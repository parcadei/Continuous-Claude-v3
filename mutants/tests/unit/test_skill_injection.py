"""Tests for skill injection into Agentica agents - TDD Implementation.

The skill injection pattern:
- Loads skill/rule content from .claude/ directory
- Prepends content to agent premise
- Supports predefined bundles (implementation, research)
- Works with DependencySwarm and other agent patterns

Test implementation follows strict TDD:
1. Write failing tests
2. Implement minimal code to pass
3. Run qlty
4. Repeat
"""

import pytest
from pathlib import Path
from unittest.mock import patch, mock_open


class TestSkillLoading:
    """Test loading individual skills and rules."""

    def test_load_skill_exists(self):
        """Should load skill content from SKILL.md file."""
        from scripts.agentica.skill_injection import load_skill

        # Use real skill from the repo
        result = load_skill("test-driven-development")

        assert result is not None
        assert len(result) > 0
        assert "TDD" in result or "test" in result.lower()

    def test_load_skill_not_found(self):
        """Should raise FileNotFoundError for non-existent skill."""
        from scripts.agentica.skill_injection import load_skill

        with pytest.raises(FileNotFoundError):
            load_skill("non-existent-skill-xyz")

    def test_load_skill_with_custom_path(self, tmp_path):
        """Should load skill from custom base path."""
        from scripts.agentica.skill_injection import load_skill

        # Create mock skill structure
        skill_dir = tmp_path / ".claude" / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("Test skill content")

        result = load_skill("test-skill", base_path=tmp_path)

        assert result == "Test skill content"

    def test_load_rule_exists(self):
        """Should load rule content from .md file."""
        from scripts.agentica.skill_injection import load_rule

        # Use real rule from the repo
        result = load_rule("git-commits")

        assert result is not None
        assert len(result) > 0
        assert "commit" in result.lower()

    def test_load_rule_not_found(self):
        """Should raise FileNotFoundError for non-existent rule."""
        from scripts.agentica.skill_injection import load_rule

        with pytest.raises(FileNotFoundError):
            load_rule("non-existent-rule-xyz")

    def test_load_rule_with_custom_path(self, tmp_path):
        """Should load rule from custom base path."""
        from scripts.agentica.skill_injection import load_rule

        # Create mock rule structure
        rules_dir = tmp_path / ".claude" / "rules"
        rules_dir.mkdir(parents=True)
        rule_file = rules_dir / "test-rule.md"
        rule_file.write_text("Test rule content")

        result = load_rule("test-rule", base_path=tmp_path)

        assert result == "Test rule content"


class TestSkillInjection:
    """Test injecting skills into agent premises."""

    def test_inject_single_skill(self):
        """Should inject single skill into premise."""
        from scripts.agentica.skill_injection import inject_skills

        original_premise = "You are a helpful assistant."

        with patch('scripts.agentica.skill_injection.load_skill', return_value="Skill content"):
            result = inject_skills(original_premise, skills=["test-skill"])

        assert "Skill content" in result
        assert original_premise in result
        # Skill should come before original premise
        assert result.index("Skill content") < result.index(original_premise)

    def test_inject_multiple_skills(self):
        """Should inject multiple skills in order."""
        from scripts.agentica.skill_injection import inject_skills

        original_premise = "You are a helpful assistant."

        def mock_load_skill(skill_name, base_path=None):
            return f"Content of {skill_name}"

        with patch('scripts.agentica.skill_injection.load_skill', side_effect=mock_load_skill):
            result = inject_skills(
                original_premise,
                skills=["skill-a", "skill-b"]
            )

        assert "Content of skill-a" in result
        assert "Content of skill-b" in result
        assert original_premise in result

    def test_inject_single_rule(self):
        """Should inject single rule into premise."""
        from scripts.agentica.skill_injection import inject_skills

        original_premise = "You are a helpful assistant."

        with patch('scripts.agentica.skill_injection.load_rule', return_value="Rule content"):
            result = inject_skills(original_premise, rules=["test-rule"])

        assert "Rule content" in result
        assert original_premise in result

    def test_inject_skills_and_rules(self):
        """Should inject both skills and rules."""
        from scripts.agentica.skill_injection import inject_skills

        original_premise = "You are a helpful assistant."

        with patch('scripts.agentica.skill_injection.load_skill', return_value="Skill content"), \
             patch('scripts.agentica.skill_injection.load_rule', return_value="Rule content"):
            result = inject_skills(
                original_premise,
                skills=["test-skill"],
                rules=["test-rule"]
            )

        assert "Skill content" in result
        assert "Rule content" in result
        assert original_premise in result

    def test_inject_implementation_bundle(self):
        """Should inject implementation bundle (skills + rules)."""
        from scripts.agentica.skill_injection import inject_skills

        original_premise = "Implement feature X."

        def mock_load_skill(skill_name, base_path=None):
            return f"Skill: {skill_name}"

        def mock_load_rule(rule_name, base_path=None):
            return f"Rule: {rule_name}"

        with patch('scripts.agentica.skill_injection.load_skill', side_effect=mock_load_skill), \
             patch('scripts.agentica.skill_injection.load_rule', side_effect=mock_load_rule):
            result = inject_skills(original_premise, bundle="implementation")

        # Implementation bundle should include TDD, observe-before-editing, qlty-check, git-commits
        assert "Skill: test-driven-development" in result
        assert "Skill: observe-before-editing" in result
        assert "Skill: qlty-check" in result
        assert "Rule: git-commits" in result
        assert original_premise in result

    def test_inject_research_bundle(self):
        """Should inject research bundle."""
        from scripts.agentica.skill_injection import inject_skills

        original_premise = "Research topic Y."

        def mock_load_skill(skill_name, base_path=None):
            return f"Skill: {skill_name}"

        with patch('scripts.agentica.skill_injection.load_skill', side_effect=mock_load_skill), \
             patch('scripts.agentica.skill_injection.load_rule'):
            result = inject_skills(original_premise, bundle="research")

        # Research bundle should include rp-explorer, repo-research-analyst
        assert "Skill: rp-explorer" in result
        assert "Skill: repo-research-analyst" in result
        assert original_premise in result

    def test_bundle_overrides_explicit_skills(self):
        """Bundle should override explicit skills parameter."""
        from scripts.agentica.skill_injection import inject_skills

        original_premise = "Do something."

        def mock_load_skill(skill_name, base_path=None):
            return f"Skill: {skill_name}"

        def mock_load_rule(rule_name, base_path=None):
            return f"Rule: {rule_name}"

        with patch('scripts.agentica.skill_injection.load_skill', side_effect=mock_load_skill), \
             patch('scripts.agentica.skill_injection.load_rule', side_effect=mock_load_rule):
            result = inject_skills(
                original_premise,
                skills=["should-be-ignored"],
                bundle="implementation"
            )

        # Bundle skills should be used, not explicit skills
        assert "Skill: test-driven-development" in result
        assert "should-be-ignored" not in result

    def test_inject_with_empty_lists(self):
        """Should return original premise if no skills/rules."""
        from scripts.agentica.skill_injection import inject_skills

        original_premise = "You are a helpful assistant."

        result = inject_skills(original_premise, skills=[], rules=[])

        assert result == original_premise

    def test_inject_with_none_parameters(self):
        """Should return original premise if skills/rules are None."""
        from scripts.agentica.skill_injection import inject_skills

        original_premise = "You are a helpful assistant."

        result = inject_skills(original_premise, skills=None, rules=None)

        assert result == original_premise


class TestBundleDefinitions:
    """Test predefined bundle definitions."""

    def test_implementation_bundle_structure(self):
        """Implementation bundle should have correct structure."""
        from scripts.agentica.skill_injection import BUNDLES

        bundle = BUNDLES.get("implementation")

        assert bundle is not None
        assert "skills" in bundle
        assert "rules" in bundle
        assert "premise" in bundle
        assert isinstance(bundle["skills"], list)
        assert isinstance(bundle["rules"], list)

    def test_research_bundle_structure(self):
        """Research bundle should have correct structure."""
        from scripts.agentica.skill_injection import BUNDLES

        bundle = BUNDLES.get("research")

        assert bundle is not None
        assert "skills" in bundle
        assert "rules" in bundle
        assert "premise" in bundle
