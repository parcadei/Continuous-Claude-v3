"""
Test that skill-rules.json contains agent triggers for kraken, validator, and scribe agents.

These agents should be invoked via Task tool with appropriate trigger patterns:
- kraken: implementation/coding tasks (implement, build, refactor, code this)
- validator: testing/validation tasks (validate, run tests, check tests, verify)
- scribe: documentation tasks (document, handoff, write docs, summarize session)
"""

import json
import re
from pathlib import Path

import pytest


def load_skill_rules() -> dict:
    """Load skill-rules.json from the project."""
    skill_rules_path = Path(__file__).parent.parent.parent / ".claude" / "skills" / "skill-rules.json"
    with open(skill_rules_path) as f:
        return json.load(f)


class TestAgentTriggers:
    """Test that agent triggers are properly configured in skill-rules.json."""

    @pytest.fixture
    def skill_rules(self) -> dict:
        return load_skill_rules()

    def test_kraken_agent_exists(self, skill_rules: dict) -> None:
        """Kraken agent should be registered in the agents section."""
        agents = skill_rules.get("agents", {})
        assert "kraken" in agents, "kraken agent not found in skill-rules.json agents section"

    def test_validator_agent_exists(self, skill_rules: dict) -> None:
        """Validator agent should be registered in the agents section."""
        agents = skill_rules.get("agents", {})
        assert "validator" in agents, "validator agent not found in skill-rules.json agents section"

    def test_scribe_agent_exists(self, skill_rules: dict) -> None:
        """Scribe agent should be registered in the agents section."""
        agents = skill_rules.get("agents", {})
        assert "scribe" in agents, "scribe agent not found in skill-rules.json agents section"

    def test_kraken_trigger_keywords(self, skill_rules: dict) -> None:
        """Kraken should trigger on implementation/coding keywords."""
        kraken = skill_rules.get("agents", {}).get("kraken", {})
        triggers = kraken.get("promptTriggers", {})
        keywords = triggers.get("keywords", [])

        expected_keywords = ["implement", "build", "refactor", "code this"]
        for kw in expected_keywords:
            assert any(kw.lower() in k.lower() for k in keywords), \
                f"kraken missing keyword trigger for '{kw}'"

    def test_validator_trigger_keywords(self, skill_rules: dict) -> None:
        """Validator should trigger on testing/validation keywords."""
        validator = skill_rules.get("agents", {}).get("validator", {})
        triggers = validator.get("promptTriggers", {})
        keywords = triggers.get("keywords", [])

        expected_keywords = ["validate", "run tests", "check tests", "verify"]
        for kw in expected_keywords:
            assert any(kw.lower() in k.lower() for k in keywords), \
                f"validator missing keyword trigger for '{kw}'"

    def test_scribe_trigger_keywords(self, skill_rules: dict) -> None:
        """Scribe should trigger on documentation keywords."""
        scribe = skill_rules.get("agents", {}).get("scribe", {})
        triggers = scribe.get("promptTriggers", {})
        keywords = triggers.get("keywords", [])

        expected_keywords = ["document", "handoff", "write docs", "summarize session"]
        for kw in expected_keywords:
            assert any(kw.lower() in k.lower() for k in keywords), \
                f"scribe missing keyword trigger for '{kw}'"

    def test_kraken_has_intent_patterns(self, skill_rules: dict) -> None:
        """Kraken should have intent patterns for regex matching."""
        kraken = skill_rules.get("agents", {}).get("kraken", {})
        triggers = kraken.get("promptTriggers", {})
        patterns = triggers.get("intentPatterns", [])

        assert len(patterns) > 0, "kraken should have at least one intent pattern"

        # Test that patterns match expected phrases
        test_phrases = ["implement this feature", "build the component", "refactor the code"]
        for phrase in test_phrases:
            matched = any(re.search(p, phrase, re.IGNORECASE) for p in patterns)
            assert matched, f"kraken intent patterns should match '{phrase}'"

    def test_validator_has_intent_patterns(self, skill_rules: dict) -> None:
        """Validator should have intent patterns for regex matching."""
        validator = skill_rules.get("agents", {}).get("validator", {})
        triggers = validator.get("promptTriggers", {})
        patterns = triggers.get("intentPatterns", [])

        assert len(patterns) > 0, "validator should have at least one intent pattern"

        # Test that patterns match expected phrases
        test_phrases = ["run the tests", "verify this works", "check tests pass"]
        for phrase in test_phrases:
            matched = any(re.search(p, phrase, re.IGNORECASE) for p in patterns)
            assert matched, f"validator intent patterns should match '{phrase}'"

    def test_scribe_has_intent_patterns(self, skill_rules: dict) -> None:
        """Scribe should have intent patterns for regex matching."""
        scribe = skill_rules.get("agents", {}).get("scribe", {})
        triggers = scribe.get("promptTriggers", {})
        patterns = triggers.get("intentPatterns", [])

        assert len(patterns) > 0, "scribe should have at least one intent pattern"

        # Test that patterns match expected phrases
        test_phrases = ["document this", "create handoff", "summarize the session"]
        for phrase in test_phrases:
            matched = any(re.search(p, phrase, re.IGNORECASE) for p in patterns)
            assert matched, f"scribe intent patterns should match '{phrase}'"

    def test_agents_have_required_fields(self, skill_rules: dict) -> None:
        """All three agents should have required configuration fields."""
        agents = skill_rules.get("agents", {})
        required_fields = ["type", "enforcement", "priority", "description", "promptTriggers"]

        for agent_name in ["kraken", "validator", "scribe"]:
            agent = agents.get(agent_name, {})
            for field in required_fields:
                assert field in agent, f"{agent_name} agent missing required field '{field}'"

    def test_agents_have_valid_priority(self, skill_rules: dict) -> None:
        """All three agents should have valid priority levels."""
        agents = skill_rules.get("agents", {})
        valid_priorities = ["critical", "high", "medium", "low"]

        for agent_name in ["kraken", "validator", "scribe"]:
            agent = agents.get(agent_name, {})
            priority = agent.get("priority")
            assert priority in valid_priorities, \
                f"{agent_name} agent has invalid priority '{priority}'"
