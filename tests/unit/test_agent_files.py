"""Tests for agent file structure and content validation."""

import re
from pathlib import Path

import pytest

# Base path for agent files
AGENTS_DIR = Path(__file__).parent.parent.parent / ".claude" / "agents"


class TestScribeAgent:
    """Tests for the scribe agent file."""

    @pytest.fixture
    def scribe_path(self) -> Path:
        """Path to scribe agent file."""
        return AGENTS_DIR / "scribe.md"

    def test_scribe_agent_exists(self, scribe_path: Path) -> None:
        """Scribe agent file must exist."""
        assert scribe_path.exists(), f"Scribe agent file not found at {scribe_path}"

    def test_scribe_has_frontmatter(self, scribe_path: Path) -> None:
        """Scribe agent must have YAML frontmatter."""
        content = scribe_path.read_text()
        assert content.startswith("---"), "Agent file must start with YAML frontmatter"
        # Find the closing ---
        second_delimiter = content.find("---", 3)
        assert second_delimiter > 0, "Agent file must have closing frontmatter delimiter"

    def test_scribe_has_required_frontmatter_fields(self, scribe_path: Path) -> None:
        """Scribe agent frontmatter must have name, description, and tools."""
        content = scribe_path.read_text()
        frontmatter_end = content.find("---", 3)
        frontmatter = content[4:frontmatter_end]

        assert "name:" in frontmatter, "Frontmatter must include 'name:'"
        assert "description:" in frontmatter, "Frontmatter must include 'description:'"
        assert "tools:" in frontmatter, "Frontmatter must include 'tools:'"

    def test_scribe_has_description_section(self, scribe_path: Path) -> None:
        """Scribe agent must have a description heading or intro."""
        content = scribe_path.read_text()
        # Should have a main heading for the agent
        assert "# Scribe Agent" in content or "# scribe" in content.lower(), \
            "Agent file must have a main heading"

    def test_scribe_mentions_documentation_role(self, scribe_path: Path) -> None:
        """Scribe agent should mention documentation as its role."""
        content = scribe_path.read_text().lower()
        doc_keywords = ["documentation", "document", "handoff", "ledger", "summary", "scribe"]
        found = any(kw in content for kw in doc_keywords)
        assert found, "Scribe agent must mention documentation/handoff role"

    def test_scribe_has_workflow_section(self, scribe_path: Path) -> None:
        """Scribe agent should have workflow or step instructions."""
        content = scribe_path.read_text()
        # Check for workflow-like sections
        workflow_patterns = [
            r"## Step \d",
            r"## Workflow",
            r"## Output",
            r"## Rules",
        ]
        found = any(re.search(p, content) for p in workflow_patterns)
        assert found, "Scribe agent must have workflow/step sections"

    def test_scribe_tools_include_write_and_read(self, scribe_path: Path) -> None:
        """Scribe agent tools should include Write and Read for documentation."""
        content = scribe_path.read_text()
        frontmatter_end = content.find("---", 3)
        frontmatter = content[4:frontmatter_end]

        # Find the tools line
        tools_match = re.search(r"tools:\s*\[([^\]]+)\]", frontmatter)
        assert tools_match, "Could not find tools list in frontmatter"

        tools = tools_match.group(1)
        assert "Write" in tools, "Scribe agent must have Write tool"
        assert "Read" in tools, "Scribe agent must have Read tool"

    def test_scribe_mentions_shared_scope(self, scribe_path: Path) -> None:
        """Scribe agent should reference shared scope (thoughts/, docs/)."""
        content = scribe_path.read_text()
        shared_keywords = ["thoughts/", "shared", "handoff", "docs/"]
        found = any(kw in content for kw in shared_keywords)
        assert found, "Scribe agent should reference shared directories (thoughts/, docs/)"


class TestValidatorAgent:
    """Tests for the validator agent file (test runner and implementation validator)."""

    @pytest.fixture
    def validator_path(self) -> Path:
        """Path to validator agent file."""
        return AGENTS_DIR / "validator.md"

    def test_validator_agent_exists(self, validator_path: Path) -> None:
        """Validator agent file must exist."""
        assert validator_path.exists(), f"Validator agent file not found at {validator_path}"

    def test_validator_has_frontmatter(self, validator_path: Path) -> None:
        """Validator agent must have YAML frontmatter."""
        content = validator_path.read_text()
        assert content.startswith("---"), "Agent file must start with YAML frontmatter"
        second_delimiter = content.find("---", 3)
        assert second_delimiter > 0, "Agent file must have closing frontmatter delimiter"

    def test_validator_has_required_frontmatter_fields(self, validator_path: Path) -> None:
        """Validator agent frontmatter must have name, description, and tools."""
        content = validator_path.read_text()
        frontmatter_end = content.find("---", 3)
        frontmatter = content[4:frontmatter_end]

        assert "name:" in frontmatter, "Frontmatter must include 'name:'"
        assert "description:" in frontmatter, "Frontmatter must include 'description:'"
        assert "tools:" in frontmatter, "Frontmatter must include 'tools:'"

    def test_validator_has_description_section(self, validator_path: Path) -> None:
        """Validator agent must have a description heading."""
        content = validator_path.read_text()
        assert "# Validator Agent" in content or "# validator" in content.lower(), \
            "Agent file must have a main heading"

    def test_validator_mentions_testing_role(self, validator_path: Path) -> None:
        """Validator agent should mention test running and validation."""
        content = validator_path.read_text().lower()
        # Must mention testing
        assert "test" in content, "Validator agent must mention testing"
        # Must mention validation/verification
        validation_keywords = ["validate", "validation", "verify", "verification"]
        found = any(kw in content for kw in validation_keywords)
        assert found, "Validator agent must mention validation/verification"

    def test_validator_has_workflow_section(self, validator_path: Path) -> None:
        """Validator agent should have workflow or step instructions."""
        content = validator_path.read_text()
        workflow_patterns = [
            r"## Step \d",
            r"## Workflow",
            r"## Output",
            r"## Rules",
        ]
        found = any(re.search(p, content) for p in workflow_patterns)
        assert found, "Validator agent must have workflow/step sections"

    def test_validator_has_output_section(self, validator_path: Path) -> None:
        """Validator agent should specify output format."""
        content = validator_path.read_text()
        assert "Output" in content or "output" in content, \
            "Validator agent must specify output format"

    def test_validator_tools_include_bash(self, validator_path: Path) -> None:
        """Validator agent must have Bash tool for running tests."""
        content = validator_path.read_text()
        frontmatter_end = content.find("---", 3)
        frontmatter = content[4:frontmatter_end]

        tools_match = re.search(r"tools:\s*\[([^\]]+)\]", frontmatter)
        assert tools_match, "Could not find tools list in frontmatter"

        tools = tools_match.group(1)
        assert "Bash" in tools, "Validator agent must have Bash tool for running tests"

    def test_validator_tools_include_write(self, validator_path: Path) -> None:
        """Validator agent must have Write tool for reports."""
        content = validator_path.read_text()
        frontmatter_end = content.find("---", 3)
        frontmatter = content[4:frontmatter_end]

        tools_match = re.search(r"tools:\s*\[([^\]]+)\]", frontmatter)
        assert tools_match, "Could not find tools list in frontmatter"

        tools = tools_match.group(1)
        assert "Write" in tools, "Validator agent must have Write tool for reports"

    def test_validator_tools_include_read(self, validator_path: Path) -> None:
        """Validator agent must have Read tool for reading tests."""
        content = validator_path.read_text()
        frontmatter_end = content.find("---", 3)
        frontmatter = content[4:frontmatter_end]

        tools_match = re.search(r"tools:\s*\[([^\]]+)\]", frontmatter)
        assert tools_match, "Could not find tools list in frontmatter"

        tools = tools_match.group(1)
        assert "Read" in tools, "Validator agent must have Read tool for reading tests"


class TestKrakenAgent:
    """Tests for the kraken agent file (implementation and refactoring)."""

    @pytest.fixture
    def kraken_path(self) -> Path:
        """Path to kraken agent file."""
        return AGENTS_DIR / "kraken.md"

    def test_kraken_agent_exists(self, kraken_path: Path) -> None:
        """Kraken agent file must exist."""
        assert kraken_path.exists(), f"Kraken agent file not found at {kraken_path}"

    def test_kraken_has_frontmatter(self, kraken_path: Path) -> None:
        """Kraken agent must have YAML frontmatter."""
        content = kraken_path.read_text()
        assert content.startswith("---"), "Agent file must start with YAML frontmatter"
        second_delimiter = content.find("---", 3)
        assert second_delimiter > 0, "Agent file must have closing frontmatter delimiter"

    def test_kraken_has_required_frontmatter_fields(self, kraken_path: Path) -> None:
        """Kraken agent frontmatter must have name, description, and tools."""
        content = kraken_path.read_text()
        frontmatter_end = content.find("---", 3)
        frontmatter = content[4:frontmatter_end]

        assert "name:" in frontmatter, "Frontmatter must include 'name:'"
        assert "description:" in frontmatter, "Frontmatter must include 'description:'"
        assert "tools:" in frontmatter, "Frontmatter must include 'tools:'"

    def test_kraken_has_heading(self, kraken_path: Path) -> None:
        """Kraken agent must have a main heading."""
        content = kraken_path.read_text()
        assert "# Kraken" in content, "Agent file must have '# Kraken' heading"

    def test_kraken_mentions_implementation_role(self, kraken_path: Path) -> None:
        """Kraken agent should mention implementation as its role."""
        content = kraken_path.read_text().lower()
        impl_keywords = ["implementation", "implement", "refactor"]
        found = any(kw in content for kw in impl_keywords)
        assert found, "Kraken agent must mention implementation/refactoring role"

    def test_kraken_mentions_tdd(self, kraken_path: Path) -> None:
        """Kraken agent should mention TDD workflow."""
        content = kraken_path.read_text().lower()
        tdd_keywords = ["tdd", "test-driven", "test driven", "tests first"]
        found = any(kw in content for kw in tdd_keywords)
        assert found, "Kraken agent must mention TDD approach"

    def test_kraken_has_workflow_section(self, kraken_path: Path) -> None:
        """Kraken agent should have workflow or step instructions."""
        content = kraken_path.read_text()
        workflow_patterns = [
            r"## Step \d",
            r"## Workflow",
            r"## TDD",
            r"## Rules",
        ]
        found = any(re.search(p, content) for p in workflow_patterns)
        assert found, "Kraken agent must have workflow/step sections"

    def test_kraken_has_open_tools(self, kraken_path: Path) -> None:
        """Kraken agent should have open tool access for implementation."""
        content = kraken_path.read_text()
        frontmatter_end = content.find("---", 3)
        frontmatter = content[4:frontmatter_end]

        tools_match = re.search(r"tools:\s*\[([^\]]+)\]", frontmatter)
        assert tools_match, "Could not find tools list in frontmatter"

        tools = tools_match.group(1)
        assert "Edit" in tools or "Write" in tools, \
            "Kraken agent must have Edit or Write tools for implementation"
        assert "Read" in tools, "Kraken agent must have Read tool"
        assert "Bash" in tools, "Kraken agent must have Bash tool for running tests"


class TestAgentFileFormat:
    """Generic tests for agent file format consistency."""

    @pytest.fixture
    def all_agent_files(self) -> list[Path]:
        """Get all agent markdown files."""
        if not AGENTS_DIR.exists():
            pytest.skip("Agents directory does not exist")
        return list(AGENTS_DIR.glob("*.md"))

    def test_agents_directory_exists(self) -> None:
        """Agents directory must exist."""
        assert AGENTS_DIR.exists(), f"Agents directory not found at {AGENTS_DIR}"

    def test_all_agents_have_frontmatter(self, all_agent_files: list[Path]) -> None:
        """All agent files must have YAML frontmatter."""
        for agent_file in all_agent_files:
            content = agent_file.read_text()
            assert content.startswith("---"), \
                f"{agent_file.name}: must start with YAML frontmatter"
            second_delimiter = content.find("---", 3)
            assert second_delimiter > 0, \
                f"{agent_file.name}: must have closing frontmatter delimiter"
