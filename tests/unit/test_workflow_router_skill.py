"""Tests for workflow-router skill (Phases 7-11).

TDD approach: tests written FIRST to validate:
1. SKILL.md exists with proper structure
2. Has YAML frontmatter with name, description
3. Contains goal selection section (Research/Plan/Build/Fix options)
4. Contains resource allocation section (Conservative/Balanced/Aggressive)
5. Contains plan detection logic (checks thoughts/shared/plans/)
6. Contains specialist mapping (Librarian->research-agent, etc.)
7. Workflow-router trigger exists in skill-rules.json
"""

import json
import re
from pathlib import Path

import pytest
import yaml


# =============================================================================
# Constants
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent.parent / ".claude" / "skills" / "workflow-router"
SKILL_FILE = SKILL_DIR / "SKILL.md"
SKILL_RULES_FILE = Path(__file__).parent.parent.parent / ".claude" / "skills" / "skill-rules.json"


# =============================================================================
# Test SKILL.md Existence and Structure
# =============================================================================


class TestSkillFileExists:
    """Tests for workflow-router SKILL.md existence."""

    def test_skill_directory_exists(self) -> None:
        """Skill directory should exist at .claude/skills/workflow-router/."""
        assert SKILL_DIR.exists(), f"Skill directory not found at {SKILL_DIR}"
        assert SKILL_DIR.is_dir(), f"{SKILL_DIR} should be a directory"

    def test_skill_file_exists(self) -> None:
        """SKILL.md should exist in the skill directory."""
        assert SKILL_FILE.exists(), f"SKILL.md not found at {SKILL_FILE}"
        assert SKILL_FILE.is_file(), f"{SKILL_FILE} should be a file"


# =============================================================================
# Test YAML Frontmatter
# =============================================================================


class TestYAMLFrontmatter:
    """Tests for YAML frontmatter structure."""

    def _extract_frontmatter(self, content: str) -> dict:
        """Extract YAML frontmatter from markdown content."""
        if not content.startswith("---"):
            return {}

        # Find the closing ---
        lines = content.split("\n")
        end_idx = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end_idx = i
                break

        if end_idx is None:
            return {}

        yaml_content = "\n".join(lines[1:end_idx])
        return yaml.safe_load(yaml_content) or {}

    def test_has_yaml_frontmatter(self) -> None:
        """SKILL.md should start with YAML frontmatter."""
        content = SKILL_FILE.read_text()
        assert content.startswith("---"), "SKILL.md must start with YAML frontmatter (---)"

    def test_frontmatter_has_name(self) -> None:
        """Frontmatter should have 'name' field set to 'workflow-router'."""
        content = SKILL_FILE.read_text()
        frontmatter = self._extract_frontmatter(content)
        assert "name" in frontmatter, "Frontmatter must have 'name' field"
        assert frontmatter["name"] == "workflow-router", "name should be 'workflow-router'"

    def test_frontmatter_has_description(self) -> None:
        """Frontmatter should have 'description' field."""
        content = SKILL_FILE.read_text()
        frontmatter = self._extract_frontmatter(content)
        assert "description" in frontmatter, "Frontmatter must have 'description' field"
        assert len(frontmatter["description"]) > 10, "Description should be meaningful"
        # Check it mentions goal-based or workflow orchestration
        desc_lower = frontmatter["description"].lower()
        assert any(word in desc_lower for word in ["goal", "workflow", "orchestrat"]), \
            "Description should mention goal-based workflow orchestration"


# =============================================================================
# Test Goal Selection Section
# =============================================================================


class TestGoalSelectionSection:
    """Tests for goal selection section with 4 options."""

    def test_has_goal_selection_section(self) -> None:
        """SKILL.md should have a Goal Selection section."""
        content = SKILL_FILE.read_text().lower()
        assert "goal selection" in content or "goal" in content and "selection" in content, \
            "SKILL.md must have a Goal Selection section"

    def test_has_research_option(self) -> None:
        """Goal selection should include Research option."""
        content = SKILL_FILE.read_text().lower()
        # Check for research option with appropriate description
        assert "research" in content, "Must have Research goal option"
        # Should mention understand/explore
        assert any(word in content for word in ["understand", "explore", "investigate"]), \
            "Research option should mention understand/explore"

    def test_has_plan_option(self) -> None:
        """Goal selection should include Plan option."""
        content = SKILL_FILE.read_text().lower()
        assert "plan" in content, "Must have Plan goal option"
        # Should mention design/architect
        assert any(word in content for word in ["design", "architect", "solution"]), \
            "Plan option should mention design/architect"

    def test_has_build_option(self) -> None:
        """Goal selection should include Build option."""
        content = SKILL_FILE.read_text().lower()
        assert "build" in content, "Must have Build goal option"
        # Should mention implement/code
        assert any(word in content for word in ["implement", "code", "create"]), \
            "Build option should mention implement/code"

    def test_has_fix_option(self) -> None:
        """Goal selection should include Fix option."""
        content = SKILL_FILE.read_text().lower()
        assert "fix" in content, "Must have Fix goal option"
        # Should mention debug
        assert any(word in content for word in ["debug", "fix", "issue", "problem"]), \
            "Fix option should mention debug/fix"


# =============================================================================
# Test Resource Allocation Section
# =============================================================================


class TestResourceAllocationSection:
    """Tests for resource allocation section with 3 options."""

    def test_has_resource_allocation_section(self) -> None:
        """SKILL.md should have a Resource Allocation section."""
        content = SKILL_FILE.read_text().lower()
        assert "resource" in content or "allocation" in content, \
            "SKILL.md must have a Resource Allocation section"

    def test_has_conservative_option(self) -> None:
        """Resource allocation should include Conservative option."""
        content = SKILL_FILE.read_text().lower()
        assert "conservative" in content, "Must have Conservative resource option"
        # Should mention 1-2 agents
        assert any(phrase in content for phrase in ["1-2", "one or two", "minimal", "single"]), \
            "Conservative should mention 1-2 agents"

    def test_has_balanced_option(self) -> None:
        """Resource allocation should include Balanced option."""
        content = SKILL_FILE.read_text().lower()
        assert "balanced" in content, "Must have Balanced resource option"
        # Should mention recommended
        assert "recommend" in content, "Balanced should be marked as recommended"

    def test_has_aggressive_option(self) -> None:
        """Resource allocation should include Aggressive option."""
        content = SKILL_FILE.read_text().lower()
        assert "aggressive" in content, "Must have Aggressive resource option"
        # Should mention max parallel
        assert any(phrase in content for phrase in ["max", "maximum", "parallel", "full"]), \
            "Aggressive should mention max parallel"


# =============================================================================
# Test Plan Detection Logic
# =============================================================================


class TestPlanDetectionSection:
    """Tests for plan detection logic."""

    def test_has_plan_detection(self) -> None:
        """SKILL.md should check for existing plans."""
        content = SKILL_FILE.read_text()
        # Should reference the plans directory
        assert "thoughts/shared/plans" in content, \
            "Must reference thoughts/shared/plans/ directory"

    def test_checks_for_existing_plans(self) -> None:
        """Should have logic to check for existing plans."""
        content = SKILL_FILE.read_text().lower()
        # Should mention checking/detecting/finding plans
        assert any(word in content for word in ["check", "detect", "find", "exist", "look for"]), \
            "Should have logic to check for existing plans"
        assert "plan" in content, "Should reference plans"


# =============================================================================
# Test Specialist Mapping
# =============================================================================


class TestSpecialistMapping:
    """Tests for specialist mapping table."""

    def test_has_specialist_mapping(self) -> None:
        """SKILL.md should have specialist mapping section."""
        content = SKILL_FILE.read_text().lower()
        # Should have some kind of mapping section
        assert any(word in content for word in ["mapping", "specialist", "agent"]), \
            "Should have specialist mapping section"

    def test_research_maps_to_research_agent(self) -> None:
        """Research goal should map to research-agent (Librarian)."""
        content = SKILL_FILE.read_text().lower()
        # Should connect research to research-agent or Librarian
        assert "research-agent" in content or "librarian" in content, \
            "Research should map to research-agent or Librarian"

    def test_plan_maps_to_plan_agent(self) -> None:
        """Plan goal should map to plan-agent (Oracle)."""
        content = SKILL_FILE.read_text().lower()
        # Should connect plan to plan-agent or Oracle
        assert "plan-agent" in content or "oracle" in content, \
            "Plan should map to plan-agent or Oracle"

    def test_build_maps_to_kraken(self) -> None:
        """Build goal should map to kraken."""
        content = SKILL_FILE.read_text().lower()
        # Should connect build to kraken
        assert "kraken" in content, "Build should map to kraken"

    def test_fix_maps_to_debug_agent(self) -> None:
        """Fix goal should map to debug-agent (Sentinel)."""
        content = SKILL_FILE.read_text().lower()
        # Should connect fix to debug-agent or Sentinel
        assert "debug-agent" in content or "sentinel" in content, \
            "Fix should map to debug-agent or Sentinel"


# =============================================================================
# Test Confirmation Step
# =============================================================================


class TestConfirmationStep:
    """Tests for confirmation step."""

    def test_has_confirmation_step(self) -> None:
        """SKILL.md should have a confirmation step before execution."""
        content = SKILL_FILE.read_text().lower()
        # Should mention confirmation
        assert any(word in content for word in ["confirm", "approval", "proceed"]), \
            "Should have confirmation step"

    def test_shows_what_will_run(self) -> None:
        """Confirmation should show what will run."""
        content = SKILL_FILE.read_text().lower()
        # Should indicate showing/displaying the plan
        assert any(phrase in content for phrase in ["show", "display", "what will", "summary"]), \
            "Should show what will run before confirmation"


# =============================================================================
# Test Trigger in skill-rules.json
# =============================================================================


class TestSkillRulesTrigger:
    """Tests for workflow-router trigger in skill-rules.json."""

    def test_skill_rules_has_workflow_router(self) -> None:
        """skill-rules.json should have workflow-router entry."""
        assert SKILL_RULES_FILE.exists(), f"skill-rules.json not found at {SKILL_RULES_FILE}"

        with open(SKILL_RULES_FILE) as f:
            rules = json.load(f)

        skills = rules.get("skills", {})
        assert "workflow-router" in skills, \
            "skill-rules.json must have 'workflow-router' entry in skills"

    def test_trigger_has_keywords(self) -> None:
        """workflow-router trigger should have keywords."""
        with open(SKILL_RULES_FILE) as f:
            rules = json.load(f)

        skill = rules.get("skills", {}).get("workflow-router", {})
        triggers = skill.get("promptTriggers", {})
        keywords = triggers.get("keywords", [])

        assert len(keywords) > 0, "workflow-router must have keywords"
        # Should include workflow-related keywords
        keyword_str = " ".join(k.lower() for k in keywords)
        assert "workflow" in keyword_str, "Keywords should include 'workflow'"

    def test_trigger_has_intent_patterns(self) -> None:
        """workflow-router trigger should have intent patterns."""
        with open(SKILL_RULES_FILE) as f:
            rules = json.load(f)

        skill = rules.get("skills", {}).get("workflow-router", {})
        triggers = skill.get("promptTriggers", {})
        patterns = triggers.get("intentPatterns", [])

        # Intent patterns are optional but recommended
        # At least check the structure is valid
        assert isinstance(patterns, list), "intentPatterns should be a list"

    def test_trigger_has_description(self) -> None:
        """workflow-router trigger should have description."""
        with open(SKILL_RULES_FILE) as f:
            rules = json.load(f)

        skill = rules.get("skills", {}).get("workflow-router", {})
        assert "description" in skill, "workflow-router must have description"

        desc = skill["description"].lower()
        assert any(word in desc for word in ["goal", "workflow", "orchestrat"]), \
            "Description should mention goal-based workflow orchestration"
