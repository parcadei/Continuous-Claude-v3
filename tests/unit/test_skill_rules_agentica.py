"""Tests for skill-rules.json agentica configuration (Phase 7).

These tests validate the structure and content of skill-rules.json
for the agentica orchestration feature.

Tests are designed to FAIL initially (TDD approach) until Phase 7 is implemented.
"""

import json
from pathlib import Path

import pytest


class TestSkillRulesJsonValidity:
    """Tests for skill-rules.json structural validity."""

    @pytest.fixture
    def skill_rules_path(self) -> Path:
        """Path to skill-rules.json."""
        return Path(__file__).parents[2] / ".claude" / "skills" / "skill-rules.json"

    def test_skill_rules_json_exists(self, skill_rules_path: Path) -> None:
        """Verify skill-rules.json exists."""
        assert skill_rules_path.exists(), (
            f"skill-rules.json not found at {skill_rules_path}"
        )

    def test_skill_rules_json_valid(self, skill_rules_path: Path) -> None:
        """Verify skill-rules.json is valid JSON."""
        with open(skill_rules_path) as f:
            try:
                content = json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"skill-rules.json is not valid JSON: {e}")

        # Basic structure checks
        assert isinstance(content, dict), "skill-rules.json should be a dict"

    def test_skill_rules_has_version(self, skill_rules_path: Path) -> None:
        """Verify skill-rules.json has version field."""
        with open(skill_rules_path) as f:
            content = json.load(f)

        assert "version" in content, (
            "skill-rules.json should have a 'version' field"
        )

    def test_skill_rules_has_agents_section(self, skill_rules_path: Path) -> None:
        """Verify skill-rules.json has agents section."""
        with open(skill_rules_path) as f:
            content = json.load(f)

        assert "agents" in content, (
            "skill-rules.json should have an 'agents' section"
        )
        assert isinstance(content["agents"], dict), (
            "agents section should be a dict"
        )


class TestAgenticaOrchestratorAgentDefinition:
    """Tests for agentica-orchestrator agent definition in skill-rules.json."""

    @pytest.fixture
    def skill_rules_path(self) -> Path:
        """Path to skill-rules.json."""
        return Path(__file__).parents[2] / ".claude" / "skills" / "skill-rules.json"

    @pytest.fixture
    def skill_rules(self, skill_rules_path: Path) -> dict:
        """Load skill-rules.json content."""
        with open(skill_rules_path) as f:
            return json.load(f)

    def test_agentica_orchestrator_agent_exists(self, skill_rules: dict) -> None:
        """Verify agentica-orchestrator agent is defined."""
        agents = skill_rules.get("agents", {})

        assert "agentica-orchestrator" in agents, (
            "agentica-orchestrator must be defined in agents section. "
            f"Available agents: {list(agents.keys())}"
        )

    def test_agentica_orchestrator_has_required_fields(self, skill_rules: dict) -> None:
        """Verify agentica-orchestrator has all required fields."""
        agent = skill_rules.get("agents", {}).get("agentica-orchestrator", {})

        required_fields = ["type", "enforcement", "priority", "promptTriggers"]
        missing = [f for f in required_fields if f not in agent]

        assert not missing, (
            f"agentica-orchestrator missing required fields: {missing}. "
            f"Has: {list(agent.keys())}"
        )

    def test_agentica_orchestrator_type(self, skill_rules: dict) -> None:
        """Verify agentica-orchestrator type is 'domain'."""
        agent = skill_rules.get("agents", {}).get("agentica-orchestrator", {})

        assert agent.get("type") == "domain", (
            f"Expected type 'domain', got '{agent.get('type')}'"
        )

    def test_agentica_orchestrator_enforcement(self, skill_rules: dict) -> None:
        """Verify agentica-orchestrator enforcement is 'suggest'."""
        agent = skill_rules.get("agents", {}).get("agentica-orchestrator", {})

        assert agent.get("enforcement") == "suggest", (
            f"Expected enforcement 'suggest', got '{agent.get('enforcement')}'"
        )

    def test_agentica_orchestrator_priority(self, skill_rules: dict) -> None:
        """Verify agentica-orchestrator priority is 'high'."""
        agent = skill_rules.get("agents", {}).get("agentica-orchestrator", {})

        assert agent.get("priority") == "high", (
            f"Expected priority 'high', got '{agent.get('priority')}'"
        )


class TestAgenticaKeywordsDefined:
    """Tests for agentica trigger keywords."""

    @pytest.fixture
    def skill_rules_path(self) -> Path:
        """Path to skill-rules.json."""
        return Path(__file__).parents[2] / ".claude" / "skills" / "skill-rules.json"

    @pytest.fixture
    def keywords(self, skill_rules_path: Path) -> list[str]:
        """Load keywords for agentica-orchestrator."""
        with open(skill_rules_path) as f:
            content = json.load(f)
        return content.get("agents", {}).get(
            "agentica-orchestrator", {}
        ).get("promptTriggers", {}).get("keywords", [])

    def test_keywords_list_not_empty(self, keywords: list[str]) -> None:
        """Verify keywords list is not empty."""
        assert len(keywords) > 0, (
            "agentica-orchestrator must have at least one keyword trigger"
        )

    def test_slash_agentica_keyword(self, keywords: list[str]) -> None:
        """Verify '/agentica' is a keyword."""
        assert "/agentica" in keywords, (
            f"'/agentica' must be a keyword. Got: {keywords}"
        )

    def test_launch_agentica_keyword(self, keywords: list[str]) -> None:
        """Verify 'launch agentica' is a keyword."""
        assert "launch agentica" in keywords, (
            f"'launch agentica' must be a keyword. Got: {keywords}"
        )

    def test_start_agentica_keyword(self, keywords: list[str]) -> None:
        """Verify 'start agentica' is a keyword."""
        assert "start agentica" in keywords, (
            f"'start agentica' must be a keyword. Got: {keywords}"
        )

    def test_agentica_swarm_keyword(self, keywords: list[str]) -> None:
        """Verify 'agentica swarm' is a keyword."""
        assert "agentica swarm" in keywords, (
            f"'agentica swarm' must be a keyword. Got: {keywords}"
        )

    def test_agentica_research_keyword(self, keywords: list[str]) -> None:
        """Verify 'agentica research' is a keyword."""
        assert "agentica research" in keywords, (
            f"'agentica research' must be a keyword. Got: {keywords}"
        )

    def test_multi_agent_keyword(self, keywords: list[str]) -> None:
        """Verify 'multi-agent' is a keyword."""
        assert "multi-agent" in keywords, (
            f"'multi-agent' must be a keyword. Got: {keywords}"
        )


class TestAgenticaIntentPatternsDefined:
    """Tests for agentica intent patterns."""

    @pytest.fixture
    def skill_rules_path(self) -> Path:
        """Path to skill-rules.json."""
        return Path(__file__).parents[2] / ".claude" / "skills" / "skill-rules.json"

    @pytest.fixture
    def patterns(self, skill_rules_path: Path) -> list[str]:
        """Load intent patterns for agentica-orchestrator."""
        with open(skill_rules_path) as f:
            content = json.load(f)
        return content.get("agents", {}).get(
            "agentica-orchestrator", {}
        ).get("promptTriggers", {}).get("intentPatterns", [])

    def test_patterns_list_not_empty(self, patterns: list[str]) -> None:
        """Verify intent patterns list is not empty."""
        assert len(patterns) > 0, (
            "agentica-orchestrator must have at least one intent pattern"
        )

    def test_patterns_are_valid_regex(self, patterns: list[str]) -> None:
        """Verify all intent patterns are valid regex."""
        import re

        invalid_patterns = []
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as e:
                invalid_patterns.append((pattern, str(e)))

        assert not invalid_patterns, (
            f"Invalid regex patterns: {invalid_patterns}"
        )

    def test_slash_agentica_pattern_exists(self, patterns: list[str]) -> None:
        """Verify a pattern matches '/agentica'."""
        import re

        test_string = "/agentica"
        matched = any(
            re.search(pattern, test_string, re.IGNORECASE)
            for pattern in patterns
        )

        assert matched, (
            f"No pattern matches '/agentica'. Patterns: {patterns}"
        )

    def test_launch_agentica_pattern_exists(self, patterns: list[str]) -> None:
        """Verify a pattern matches 'launch agentica'."""
        import re

        test_string = "launch agentica"
        matched = any(
            re.search(pattern, test_string, re.IGNORECASE)
            for pattern in patterns
        )

        assert matched, (
            f"No pattern matches 'launch agentica'. Patterns: {patterns}"
        )


class TestAgenticaSpawnSkill:
    """Tests for agentica-spawn skill file (Phase 9)."""

    @pytest.fixture
    def skills_dir(self) -> Path:
        """Path to skills directory."""
        return Path(__file__).parents[2] / ".claude" / "skills"

    def test_agentica_spawn_skill_dir_exists(self, skills_dir: Path) -> None:
        """Verify agentica-spawn skill directory exists."""
        skill_dir = skills_dir / "agentica-spawn"

        assert skill_dir.exists(), (
            f"agentica-spawn skill directory not found: {skill_dir}"
        )
        assert skill_dir.is_dir(), (
            f"agentica-spawn should be a directory: {skill_dir}"
        )

    def test_agentica_spawn_skill_md_exists(self, skills_dir: Path) -> None:
        """Verify agentica-spawn SKILL.md exists."""
        skill_file = skills_dir / "agentica-spawn" / "SKILL.md"

        assert skill_file.exists(), (
            f"SKILL.md not found: {skill_file}"
        )

    def test_agentica_spawn_skill_has_frontmatter(self, skills_dir: Path) -> None:
        """Verify agentica-spawn SKILL.md has YAML frontmatter."""
        skill_file = skills_dir / "agentica-spawn" / "SKILL.md"

        if not skill_file.exists():
            pytest.skip("SKILL.md doesn't exist yet")

        content = skill_file.read_text()

        # Should start with YAML frontmatter
        assert content.startswith("---"), (
            "SKILL.md should start with YAML frontmatter (---)"
        )
        # Should have closing frontmatter
        assert content.count("---") >= 2, (
            "SKILL.md should have opening and closing frontmatter (---)"
        )

    def test_agentica_spawn_skill_has_name(self, skills_dir: Path) -> None:
        """Verify agentica-spawn SKILL.md has name in frontmatter."""
        skill_file = skills_dir / "agentica-spawn" / "SKILL.md"

        if not skill_file.exists():
            pytest.skip("SKILL.md doesn't exist yet")

        content = skill_file.read_text()

        assert "name:" in content, (
            "SKILL.md frontmatter must have 'name:' field"
        )
        assert "agentica-spawn" in content, (
            "SKILL.md must reference 'agentica-spawn'"
        )

    def test_agentica_spawn_skill_has_pattern_examples(self, skills_dir: Path) -> None:
        """Verify agentica-spawn SKILL.md documents pattern examples."""
        skill_file = skills_dir / "agentica-spawn" / "SKILL.md"

        if not skill_file.exists():
            pytest.skip("SKILL.md doesn't exist yet")

        content = skill_file.read_text()

        # Should document the main patterns
        patterns = ["Swarm", "Hierarchical", "Generator", "Critic", "Jury"]
        for pattern in patterns:
            assert pattern in content, (
                f"SKILL.md should document '{pattern}' pattern"
            )

    def test_agentica_spawn_skill_mentions_swarm_id(self, skills_dir: Path) -> None:
        """Verify agentica-spawn SKILL.md mentions SWARM_ID env var."""
        skill_file = skills_dir / "agentica-spawn" / "SKILL.md"

        if not skill_file.exists():
            pytest.skip("SKILL.md doesn't exist yet")

        content = skill_file.read_text()

        assert "SWARM_ID" in content, (
            "SKILL.md should document SWARM_ID environment variable"
        )


class TestSkillRulesConsistency:
    """Tests for skill-rules.json internal consistency."""

    @pytest.fixture
    def skill_rules_path(self) -> Path:
        """Path to skill-rules.json."""
        return Path(__file__).parents[2] / ".claude" / "skills" / "skill-rules.json"

    @pytest.fixture
    def skill_rules(self, skill_rules_path: Path) -> dict:
        """Load skill-rules.json content."""
        with open(skill_rules_path) as f:
            return json.load(f)

    def test_all_agents_have_required_fields(self, skill_rules: dict) -> None:
        """Verify all agents have required fields."""
        agents = skill_rules.get("agents", {})
        required_fields = ["type", "enforcement", "priority"]

        issues = []
        for name, agent in agents.items():
            missing = [f for f in required_fields if f not in agent]
            if missing:
                issues.append(f"{name}: missing {missing}")

        assert not issues, f"Agents with missing fields: {issues}"

    def test_enforcement_values_valid(self, skill_rules: dict) -> None:
        """Verify all enforcement values are valid."""
        valid_enforcements = {"suggest", "block", "warn"}
        agents = skill_rules.get("agents", {})

        issues = []
        for name, agent in agents.items():
            enforcement = agent.get("enforcement")
            if enforcement not in valid_enforcements:
                issues.append(f"{name}: invalid enforcement '{enforcement}'")

        assert not issues, f"Invalid enforcement values: {issues}"

    def test_priority_values_valid(self, skill_rules: dict) -> None:
        """Verify all priority values are valid."""
        valid_priorities = {"critical", "high", "medium", "low"}
        agents = skill_rules.get("agents", {})

        issues = []
        for name, agent in agents.items():
            priority = agent.get("priority")
            if priority not in valid_priorities:
                issues.append(f"{name}: invalid priority '{priority}'")

        assert not issues, f"Invalid priority values: {issues}"
