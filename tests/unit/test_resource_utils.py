"""Tests for Phase 1: RAM Query Utility (resource-utils.ts).

TDD tests for the getSystemResources() function that queries system resources
using Node.js os module.

Expected function signature:
    getSystemResources(): { freeRAM: number, totalRAM: number, cpuCores: number, loadAvg: number[] }

The TypeScript module should be at:
    .claude/hooks/src/shared/resource-utils.ts

Tests invoke the TypeScript file via npx tsx and verify:
1. The function returns valid JSON with expected fields
2. RAM values are in bytes and reasonable (> 0, freeRAM <= totalRAM)
3. cpuCores is a positive integer
4. loadAvg is an array of 3 numbers (1, 5, 15 minute averages)

See plan: docs/handoffs/resource-limits-plan.md (Phase 1)
"""

import json
import os
import subprocess
from pathlib import Path

import pytest


class TestResourceUtilsFileExists:
    """Tests for resource-utils.ts file existence."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_resource_utils_file_exists(self, shared_dir: Path) -> None:
        """resource-utils.ts exists in shared directory."""
        resource_utils = shared_dir / "resource-utils.ts"

        assert resource_utils.exists(), (
            f"resource-utils.ts not found: {resource_utils}. "
            "Create .claude/hooks/src/shared/resource-utils.ts with getSystemResources() function."
        )

    def test_resource_utils_is_regular_file(self, shared_dir: Path) -> None:
        """resource-utils.ts is a regular file."""
        resource_utils = shared_dir / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        assert resource_utils.is_file(), (
            f"resource-utils.ts should be a regular file. Path: {resource_utils}"
        )


class TestResourceUtilsExportsFunction:
    """Tests for getSystemResources() function export."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_exports_get_system_resources(self, shared_dir: Path) -> None:
        """resource-utils.ts exports getSystemResources function."""
        resource_utils = shared_dir / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        content = resource_utils.read_text()

        assert "export function getSystemResources" in content or "export const getSystemResources" in content, (
            "resource-utils.ts must export getSystemResources function. "
            f"Content: {content[:500]}"
        )


class TestGetSystemResourcesOutput:
    """Tests for getSystemResources() function output."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def _get_test_script_content(self, hooks_dir: Path) -> str:
        """TypeScript test script that calls getSystemResources with absolute path."""
        resource_utils_path = hooks_dir / "src" / "shared" / "resource-utils.ts"
        return f'''
import {{ getSystemResources }} from '{resource_utils_path}';

const resources = getSystemResources();
console.log(JSON.stringify(resources));
'''

    def test_returns_valid_json(self, hooks_dir: Path, tmp_path: Path) -> None:
        """getSystemResources() returns valid JSON."""
        resource_utils = hooks_dir / "src" / "shared" / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        # Write test script with absolute path
        test_script = tmp_path / "test_runner.ts"
        test_script.write_text(self._get_test_script_content(hooks_dir))

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, (
            f"Test script failed. Exit code: {result.returncode}, "
            f"stderr: {result.stderr}, stdout: {result.stdout}"
        )

        assert result.stdout.strip(), "getSystemResources() should produce output"

        try:
            output = json.loads(result.stdout.strip())
        except json.JSONDecodeError as e:
            pytest.fail(f"Output is not valid JSON: {e}. Output: {result.stdout}")

        assert isinstance(output, dict), f"Output should be a dict. Got: {type(output)}"

    def test_has_free_ram_field(self, hooks_dir: Path, tmp_path: Path) -> None:
        """getSystemResources() returns freeRAM field."""
        resource_utils = hooks_dir / "src" / "shared" / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        test_script = tmp_path / "test_runner.ts"
        test_script.write_text(self._get_test_script_content(hooks_dir))

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            timeout=30
        )

        if result.returncode != 0:
            pytest.skip(f"Test script failed: {result.stderr}")

        output = json.loads(result.stdout.strip())

        assert "freeRAM" in output, f"Output must contain 'freeRAM' field. Got: {output}"
        assert isinstance(output["freeRAM"], (int, float)), f"freeRAM must be a number. Got: {type(output['freeRAM'])}"
        assert output["freeRAM"] > 0, f"freeRAM must be positive. Got: {output['freeRAM']}"

    def test_has_total_ram_field(self, hooks_dir: Path, tmp_path: Path) -> None:
        """getSystemResources() returns totalRAM field."""
        resource_utils = hooks_dir / "src" / "shared" / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        test_script = tmp_path / "test_runner.ts"
        test_script.write_text(self._get_test_script_content(hooks_dir))

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            timeout=30
        )

        if result.returncode != 0:
            pytest.skip(f"Test script failed: {result.stderr}")

        output = json.loads(result.stdout.strip())

        assert "totalRAM" in output, f"Output must contain 'totalRAM' field. Got: {output}"
        assert isinstance(output["totalRAM"], (int, float)), f"totalRAM must be a number. Got: {type(output['totalRAM'])}"
        assert output["totalRAM"] > 0, f"totalRAM must be positive. Got: {output['totalRAM']}"

    def test_has_cpu_cores_field(self, hooks_dir: Path, tmp_path: Path) -> None:
        """getSystemResources() returns cpuCores field."""
        resource_utils = hooks_dir / "src" / "shared" / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        test_script = tmp_path / "test_runner.ts"
        test_script.write_text(self._get_test_script_content(hooks_dir))

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            timeout=30
        )

        if result.returncode != 0:
            pytest.skip(f"Test script failed: {result.stderr}")

        output = json.loads(result.stdout.strip())

        assert "cpuCores" in output, f"Output must contain 'cpuCores' field. Got: {output}"
        assert isinstance(output["cpuCores"], int), f"cpuCores must be an integer. Got: {type(output['cpuCores'])}"
        assert output["cpuCores"] >= 1, f"cpuCores must be >= 1. Got: {output['cpuCores']}"

    def test_has_load_avg_field(self, hooks_dir: Path, tmp_path: Path) -> None:
        """getSystemResources() returns loadAvg field as array of 3 numbers."""
        resource_utils = hooks_dir / "src" / "shared" / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        test_script = tmp_path / "test_runner.ts"
        test_script.write_text(self._get_test_script_content(hooks_dir))

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            timeout=30
        )

        if result.returncode != 0:
            pytest.skip(f"Test script failed: {result.stderr}")

        output = json.loads(result.stdout.strip())

        assert "loadAvg" in output, f"Output must contain 'loadAvg' field. Got: {output}"
        assert isinstance(output["loadAvg"], list), f"loadAvg must be an array. Got: {type(output['loadAvg'])}"
        assert len(output["loadAvg"]) == 3, f"loadAvg must have 3 elements. Got: {len(output['loadAvg'])}"
        for i, val in enumerate(output["loadAvg"]):
            assert isinstance(val, (int, float)), f"loadAvg[{i}] must be a number. Got: {type(val)}"
            assert val >= 0, f"loadAvg[{i}] must be non-negative. Got: {val}"


class TestRAMValuesAreReasonable:
    """Tests for reasonable RAM values."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def _get_test_script_content(self, hooks_dir: Path) -> str:
        """TypeScript test script that calls getSystemResources with absolute path."""
        resource_utils_path = hooks_dir / "src" / "shared" / "resource-utils.ts"
        return f'''
import {{ getSystemResources }} from '{resource_utils_path}';

const resources = getSystemResources();
console.log(JSON.stringify(resources));
'''

    def test_free_ram_less_than_or_equal_total(self, hooks_dir: Path, tmp_path: Path) -> None:
        """freeRAM <= totalRAM."""
        resource_utils = hooks_dir / "src" / "shared" / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        test_script = tmp_path / "test_runner.ts"
        test_script.write_text(self._get_test_script_content(hooks_dir))

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            timeout=30
        )

        if result.returncode != 0:
            pytest.skip(f"Test script failed: {result.stderr}")

        output = json.loads(result.stdout.strip())

        assert output["freeRAM"] <= output["totalRAM"], (
            f"freeRAM ({output['freeRAM']}) must be <= totalRAM ({output['totalRAM']})"
        )

    def test_total_ram_in_reasonable_range(self, hooks_dir: Path, tmp_path: Path) -> None:
        """totalRAM is in reasonable range (512MB to 1TB in bytes)."""
        resource_utils = hooks_dir / "src" / "shared" / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        test_script = tmp_path / "test_runner.ts"
        test_script.write_text(self._get_test_script_content(hooks_dir))

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            timeout=30
        )

        if result.returncode != 0:
            pytest.skip(f"Test script failed: {result.stderr}")

        output = json.loads(result.stdout.strip())

        min_ram = 512 * 1024 * 1024  # 512 MB in bytes
        max_ram = 1024 * 1024 * 1024 * 1024  # 1 TB in bytes

        assert output["totalRAM"] >= min_ram, (
            f"totalRAM ({output['totalRAM']}) seems too low. Min expected: {min_ram} (512MB)"
        )
        assert output["totalRAM"] <= max_ram, (
            f"totalRAM ({output['totalRAM']}) seems too high. Max expected: {max_ram} (1TB)"
        )


class TestCPUValuesAreReasonable:
    """Tests for reasonable CPU values."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def _get_test_script_content(self, hooks_dir: Path) -> str:
        """TypeScript test script that calls getSystemResources with absolute path."""
        resource_utils_path = hooks_dir / "src" / "shared" / "resource-utils.ts"
        return f'''
import {{ getSystemResources }} from '{resource_utils_path}';

const resources = getSystemResources();
console.log(JSON.stringify(resources));
'''

    def test_cpu_cores_in_reasonable_range(self, hooks_dir: Path, tmp_path: Path) -> None:
        """cpuCores is in reasonable range (1 to 256)."""
        resource_utils = hooks_dir / "src" / "shared" / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        test_script = tmp_path / "test_runner.ts"
        test_script.write_text(self._get_test_script_content(hooks_dir))

        result = subprocess.run(
            ["npx", "tsx", str(test_script)],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
            timeout=30
        )

        if result.returncode != 0:
            pytest.skip(f"Test script failed: {result.stderr}")

        output = json.loads(result.stdout.strip())

        assert 1 <= output["cpuCores"] <= 256, (
            f"cpuCores ({output['cpuCores']}) should be between 1 and 256"
        )


class TestTypeScriptTypeExport:
    """Tests for SystemResources interface export."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_exports_system_resources_interface(self, shared_dir: Path) -> None:
        """resource-utils.ts exports SystemResources interface."""
        resource_utils = shared_dir / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        content = resource_utils.read_text()

        assert "export interface SystemResources" in content or "export type SystemResources" in content, (
            "resource-utils.ts should export SystemResources interface/type. "
            f"Content: {content[:500]}"
        )

    def test_interface_has_free_ram(self, shared_dir: Path) -> None:
        """SystemResources interface has freeRAM: number."""
        resource_utils = shared_dir / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        content = resource_utils.read_text()

        assert "freeRAM" in content and "number" in content, (
            "SystemResources should have freeRAM: number field"
        )

    def test_interface_has_total_ram(self, shared_dir: Path) -> None:
        """SystemResources interface has totalRAM: number."""
        resource_utils = shared_dir / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        content = resource_utils.read_text()

        assert "totalRAM" in content and "number" in content, (
            "SystemResources should have totalRAM: number field"
        )

    def test_interface_has_cpu_cores(self, shared_dir: Path) -> None:
        """SystemResources interface has cpuCores: number."""
        resource_utils = shared_dir / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        content = resource_utils.read_text()

        assert "cpuCores" in content and "number" in content, (
            "SystemResources should have cpuCores: number field"
        )

    def test_interface_has_load_avg(self, shared_dir: Path) -> None:
        """SystemResources interface has loadAvg: number[]."""
        resource_utils = shared_dir / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        content = resource_utils.read_text()

        assert "loadAvg" in content and "number[]" in content, (
            "SystemResources should have loadAvg: number[] field"
        )


class TestUsesNodeOsModule:
    """Tests that implementation uses Node.js os module."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_imports_os_module(self, shared_dir: Path) -> None:
        """resource-utils.ts imports Node.js os module."""
        resource_utils = shared_dir / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        content = resource_utils.read_text()

        assert "import" in content and "'os'" in content or '"os"' in content or "from 'os'" in content or 'from "os"' in content, (
            "resource-utils.ts should import Node.js os module. "
            f"Content: {content[:500]}"
        )

    def test_uses_os_freemem(self, shared_dir: Path) -> None:
        """resource-utils.ts uses os.freemem()."""
        resource_utils = shared_dir / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        content = resource_utils.read_text()

        assert "freemem" in content.lower() or "freemem()" in content, (
            "resource-utils.ts should use os.freemem(). "
            f"Content: {content[:500]}"
        )

    def test_uses_os_totalmem(self, shared_dir: Path) -> None:
        """resource-utils.ts uses os.totalmem()."""
        resource_utils = shared_dir / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        content = resource_utils.read_text()

        assert "totalmem" in content.lower() or "totalmem()" in content, (
            "resource-utils.ts should use os.totalmem(). "
            f"Content: {content[:500]}"
        )

    def test_uses_os_cpus(self, shared_dir: Path) -> None:
        """resource-utils.ts uses os.cpus()."""
        resource_utils = shared_dir / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        content = resource_utils.read_text()

        assert "cpus" in content.lower() or "cpus()" in content, (
            "resource-utils.ts should use os.cpus(). "
            f"Content: {content[:500]}"
        )

    def test_uses_os_loadavg(self, shared_dir: Path) -> None:
        """resource-utils.ts uses os.loadavg()."""
        resource_utils = shared_dir / "resource-utils.ts"

        if not resource_utils.exists():
            pytest.skip("resource-utils.ts doesn't exist yet")

        content = resource_utils.read_text()

        assert "loadavg" in content.lower() or "loadavg()" in content, (
            "resource-utils.ts should use os.loadavg(). "
            f"Content: {content[:500]}"
        )
