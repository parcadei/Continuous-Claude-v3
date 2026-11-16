"""Tests for Agentica trigger detection (Phase 7).

These tests verify that the agentica orchestration flow is triggered
correctly by user prompts containing keywords or matching intent patterns.

Tests are designed to FAIL initially (TDD approach) until Phase 7 is implemented.
"""

import json
import re
from pathlib import Path

import pytest


class TestAgenticaTriggerDetection:
    """Tests for agentica keyword and pattern triggers."""

    @pytest.fixture
    def skill_rules_path(self) -> Path:
        """Path to skill-rules.json."""
        return Path(__file__).parents[2] / ".claude" / "skills" / "skill-rules.json"

    @pytest.fixture
    def skill_rules(self, skill_rules_path: Path) -> dict:
        """Load skill-rules.json."""
        with open(skill_rules_path) as f:
            return json.load(f)

    def test_agentica_orchestrator_agent_exists(self, skill_rules: dict) -> None:
        """Verify agentica-orchestrator agent is defined in skill-rules.json."""
        assert "agents" in skill_rules, "skill-rules.json must have 'agents' section"
        agents = skill_rules["agents"]

        assert "agentica-orchestrator" in agents, (
            "agentica-orchestrator agent must be defined in skill-rules.json"
        )

    def test_agentica_orchestrator_has_prompt_triggers(self, skill_rules: dict) -> None:
        """Verify agentica-orchestrator has promptTriggers defined."""
        agent = skill_rules.get("agents", {}).get("agentica-orchestrator", {})

        assert "promptTriggers" in agent, (
            "agentica-orchestrator must have promptTriggers"
        )
        assert "keywords" in agent["promptTriggers"], (
            "agentica-orchestrator.promptTriggers must have keywords"
        )
        assert "intentPatterns" in agent["promptTriggers"], (
            "agentica-orchestrator.promptTriggers must have intentPatterns"
        )

    def test_agentica_keyword_triggers_slash_command(self, skill_rules: dict) -> None:
        """Test that '/agentica' is a trigger keyword."""
        agent = skill_rules.get("agents", {}).get("agentica-orchestrator", {})
        keywords = agent.get("promptTriggers", {}).get("keywords", [])

        assert "/agentica" in keywords, (
            "/agentica must be a trigger keyword for agentica-orchestrator"
        )

    def test_agentica_keyword_triggers_launch(self, skill_rules: dict) -> None:
        """Test that 'launch agentica' is a trigger keyword."""
        agent = skill_rules.get("agents", {}).get("agentica-orchestrator", {})
        keywords = agent.get("promptTriggers", {}).get("keywords", [])

        assert "launch agentica" in keywords, (
            "'launch agentica' must be a trigger keyword"
        )

    def test_agentica_keyword_triggers_start(self, skill_rules: dict) -> None:
        """Test that 'start agentica' is a trigger keyword."""
        agent = skill_rules.get("agents", {}).get("agentica-orchestrator", {})
        keywords = agent.get("promptTriggers", {}).get("keywords", [])

        assert "start agentica" in keywords, (
            "'start agentica' must be a trigger keyword"
        )

    def test_agentica_keyword_triggers_swarm(self, skill_rules: dict) -> None:
        """Test that 'agentica swarm' is a trigger keyword."""
        agent = skill_rules.get("agents", {}).get("agentica-orchestrator", {})
        keywords = agent.get("promptTriggers", {}).get("keywords", [])

        assert "agentica swarm" in keywords, (
            "'agentica swarm' must be a trigger keyword"
        )

    def test_agentica_keyword_triggers_multi_agent(self, skill_rules: dict) -> None:
        """Test that 'multi-agent' is a trigger keyword."""
        agent = skill_rules.get("agents", {}).get("agentica-orchestrator", {})
        keywords = agent.get("promptTriggers", {}).get("keywords", [])

        assert "multi-agent" in keywords, (
            "'multi-agent' must be a trigger keyword"
        )


class TestAgenticaIntentPatterns:
    """Tests for agentica intent pattern matching."""

    @pytest.fixture
    def skill_rules_path(self) -> Path:
        """Path to skill-rules.json."""
        return Path(__file__).parents[2] / ".claude" / "skills" / "skill-rules.json"

    @pytest.fixture
    def intent_patterns(self, skill_rules_path: Path) -> list[str]:
        """Load intent patterns for agentica-orchestrator."""
        with open(skill_rules_path) as f:
            rules = json.load(f)
        return rules.get("agents", {}).get(
            "agentica-orchestrator", {}
        ).get("promptTriggers", {}).get("intentPatterns", [])

    def test_intent_pattern_slash_agentica(self, intent_patterns: list[str]) -> None:
        """Test that '/agentica' matches an intent pattern."""
        prompt = "/agentica"

        matched = any(
            re.search(pattern, prompt, re.IGNORECASE)
            for pattern in intent_patterns
        )

        assert matched, (
            f"'/agentica' should match an intent pattern. "
            f"Patterns: {intent_patterns}"
        )

    def test_intent_pattern_launch_agentica(self, intent_patterns: list[str]) -> None:
        """Test that 'launch agentica' matches an intent pattern."""
        prompt = "launch agentica"

        matched = any(
            re.search(pattern, prompt, re.IGNORECASE)
            for pattern in intent_patterns
        )

        assert matched, (
            f"'launch agentica' should match an intent pattern. "
            f"Patterns: {intent_patterns}"
        )

    def test_intent_pattern_start_agentica_for(self, intent_patterns: list[str]) -> None:
        """Test that 'start agentica for my research task' matches."""
        prompt = "start agentica for my research task"

        matched = any(
            re.search(pattern, prompt, re.IGNORECASE)
            for pattern in intent_patterns
        )

        assert matched, (
            f"'start agentica for my research task' should match. "
            f"Patterns: {intent_patterns}"
        )

    def test_intent_pattern_use_agentica_to(self, intent_patterns: list[str]) -> None:
        """Test that 'use agentica to analyze this codebase' matches."""
        prompt = "use agentica to analyze this codebase"

        matched = any(
            re.search(pattern, prompt, re.IGNORECASE)
            for pattern in intent_patterns
        )

        assert matched, (
            f"'use agentica to analyze this codebase' should match. "
            f"Patterns: {intent_patterns}"
        )


class TestNonAgenticaPromptsDontTrigger:
    """Tests that non-agentica prompts don't falsely trigger."""

    @pytest.fixture
    def skill_rules_path(self) -> Path:
        """Path to skill-rules.json."""
        return Path(__file__).parents[2] / ".claude" / "skills" / "skill-rules.json"

    @pytest.fixture
    def agentica_config(self, skill_rules_path: Path) -> dict:
        """Load agentica-orchestrator config."""
        with open(skill_rules_path) as f:
            rules = json.load(f)
        return rules.get("agents", {}).get("agentica-orchestrator", {})

    def _prompt_matches_keywords(self, prompt: str, keywords: list[str]) -> bool:
        """Check if prompt matches any keyword."""
        prompt_lower = prompt.lower()
        return any(kw.lower() in prompt_lower for kw in keywords)

    def _prompt_matches_patterns(self, prompt: str, patterns: list[str]) -> bool:
        """Check if prompt matches any pattern."""
        return any(
            re.search(pattern, prompt, re.IGNORECASE)
            for pattern in patterns
        )

    def test_normal_code_question_doesnt_trigger(self, agentica_config: dict) -> None:
        """Normal coding questions should not trigger agentica."""
        prompt = "How do I write a for loop in Python?"

        keywords = agentica_config.get("promptTriggers", {}).get("keywords", [])
        patterns = agentica_config.get("promptTriggers", {}).get("intentPatterns", [])

        assert not self._prompt_matches_keywords(prompt, keywords), (
            "Normal code question should not match keywords"
        )
        assert not self._prompt_matches_patterns(prompt, patterns), (
            "Normal code question should not match patterns"
        )

    def test_debug_request_doesnt_trigger(self, agentica_config: dict) -> None:
        """Debug requests should not trigger agentica."""
        prompt = "Debug this function, it's returning None"

        keywords = agentica_config.get("promptTriggers", {}).get("keywords", [])
        patterns = agentica_config.get("promptTriggers", {}).get("intentPatterns", [])

        assert not self._prompt_matches_keywords(prompt, keywords)
        assert not self._prompt_matches_patterns(prompt, patterns)

    def test_simple_search_doesnt_trigger(self, agentica_config: dict) -> None:
        """Simple search requests should not trigger agentica."""
        prompt = "Find all files containing 'error'"

        keywords = agentica_config.get("promptTriggers", {}).get("keywords", [])
        patterns = agentica_config.get("promptTriggers", {}).get("intentPatterns", [])

        assert not self._prompt_matches_keywords(prompt, keywords)
        assert not self._prompt_matches_patterns(prompt, patterns)

    def test_commit_request_doesnt_trigger(self, agentica_config: dict) -> None:
        """Commit requests should not trigger agentica."""
        prompt = "Commit these changes with message 'fix bug'"

        keywords = agentica_config.get("promptTriggers", {}).get("keywords", [])
        patterns = agentica_config.get("promptTriggers", {}).get("intentPatterns", [])

        assert not self._prompt_matches_keywords(prompt, keywords)
        assert not self._prompt_matches_patterns(prompt, patterns)

    def test_generic_agent_mention_doesnt_trigger(self, agentica_config: dict) -> None:
        """Generic mentions of 'agent' should not trigger agentica."""
        # This prompt mentions 'agent' but not in agentica context
        prompt = "What is a user agent string?"

        keywords = agentica_config.get("promptTriggers", {}).get("keywords", [])
        patterns = agentica_config.get("promptTriggers", {}).get("intentPatterns", [])

        assert not self._prompt_matches_keywords(prompt, keywords)
        assert not self._prompt_matches_patterns(prompt, patterns)


class TestAgenticaOrchestratorConfiguration:
    """Tests for agentica-orchestrator agent configuration."""

    @pytest.fixture
    def skill_rules_path(self) -> Path:
        """Path to skill-rules.json."""
        return Path(__file__).parents[2] / ".claude" / "skills" / "skill-rules.json"

    @pytest.fixture
    def agentica_agent(self, skill_rules_path: Path) -> dict:
        """Load agentica-orchestrator agent config."""
        with open(skill_rules_path) as f:
            rules = json.load(f)
        return rules.get("agents", {}).get("agentica-orchestrator", {})

    def test_agentica_type_is_domain(self, agentica_agent: dict) -> None:
        """Agentica-orchestrator should be a domain type agent."""
        assert agentica_agent.get("type") == "domain", (
            "agentica-orchestrator should have type 'domain'"
        )

    def test_agentica_enforcement_is_suggest(self, agentica_agent: dict) -> None:
        """Agentica-orchestrator should use 'suggest' enforcement."""
        assert agentica_agent.get("enforcement") == "suggest", (
            "agentica-orchestrator should have enforcement 'suggest'"
        )

    def test_agentica_priority_is_high(self, agentica_agent: dict) -> None:
        """Agentica-orchestrator should have high priority."""
        assert agentica_agent.get("priority") == "high", (
            "agentica-orchestrator should have priority 'high'"
        )
