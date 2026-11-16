"""
Tests for Ledger Workflow State and New Codebase Detection.

TDD Red Phase: These tests define the expected API for:
1. Ledger template with "Workflow State" section (erotetic format)
2. New codebase detection function

The Workflow State section uses erotetic format:
    pattern: [workflow pattern name]
    phase: [current phase number]
    total_phases: [total phases]
    retries: [current retry count]
    max_retries: 3

    #### Resolved
    - goal: "[user's stated goal]"
    - resource_allocation: "[conservative|balanced|aggressive]"

    #### Unknowns
    - [any unresolved questions marked UNKNOWN]

    #### Last Failure
    [error context if any]

The codebase detection function:
    is_known_codebase(project_dir: str) -> bool

Theory:
    Workflow state follows the erotetic pattern from z3_erotetic.py,
    where E(X,Q) = {} means all propositions are resolved and
    implementation can proceed. Unknowns must be resolved before
    continuing.
"""

import os
import tempfile
import pytest


# =============================================================================
# Test Module Import
# =============================================================================

class TestLedgerModuleImport:
    """Tests that the ledger_workflow module can be imported."""

    def test_module_importable(self):
        """ledger_workflow module should be importable."""
        from scripts import ledger_workflow
        assert ledger_workflow is not None

    def test_is_known_codebase_function_exists(self):
        """is_known_codebase function should be exported."""
        from scripts.ledger_workflow import is_known_codebase
        assert callable(is_known_codebase)

    def test_get_workflow_state_template_exists(self):
        """get_workflow_state_template function should be exported."""
        from scripts.ledger_workflow import get_workflow_state_template
        assert callable(get_workflow_state_template)

    def test_parse_workflow_state_exists(self):
        """parse_workflow_state function should be exported."""
        from scripts.ledger_workflow import parse_workflow_state
        assert callable(parse_workflow_state)


# =============================================================================
# Test Workflow State Template Structure
# =============================================================================

class TestWorkflowStateTemplate:
    """Tests for the Workflow State section template."""

    def test_template_has_workflow_state_header(self):
        """Template should include ### Workflow State header."""
        from scripts.ledger_workflow import get_workflow_state_template

        template = get_workflow_state_template()
        assert "### Workflow State" in template

    def test_template_has_pattern_field(self):
        """Template should include pattern field."""
        from scripts.ledger_workflow import get_workflow_state_template

        template = get_workflow_state_template()
        assert "pattern:" in template

    def test_template_has_phase_field(self):
        """Template should include phase field."""
        from scripts.ledger_workflow import get_workflow_state_template

        template = get_workflow_state_template()
        assert "phase:" in template

    def test_template_has_total_phases_field(self):
        """Template should include total_phases field."""
        from scripts.ledger_workflow import get_workflow_state_template

        template = get_workflow_state_template()
        assert "total_phases:" in template

    def test_template_has_retries_field(self):
        """Template should include retries field."""
        from scripts.ledger_workflow import get_workflow_state_template

        template = get_workflow_state_template()
        assert "retries:" in template

    def test_template_has_max_retries_field(self):
        """Template should include max_retries field with default 3."""
        from scripts.ledger_workflow import get_workflow_state_template

        template = get_workflow_state_template()
        assert "max_retries:" in template

    def test_template_has_resolved_section(self):
        """Template should include #### Resolved section (erotetic)."""
        from scripts.ledger_workflow import get_workflow_state_template

        template = get_workflow_state_template()
        assert "#### Resolved" in template

    def test_template_has_unknowns_section(self):
        """Template should include #### Unknowns section (erotetic)."""
        from scripts.ledger_workflow import get_workflow_state_template

        template = get_workflow_state_template()
        assert "#### Unknowns" in template

    def test_template_has_last_failure_section(self):
        """Template should include #### Last Failure section."""
        from scripts.ledger_workflow import get_workflow_state_template

        template = get_workflow_state_template()
        assert "#### Last Failure" in template

    def test_template_resolved_has_goal(self):
        """Resolved section should include goal field."""
        from scripts.ledger_workflow import get_workflow_state_template

        template = get_workflow_state_template()
        # Should have goal in the Resolved section
        assert "goal:" in template

    def test_template_resolved_has_resource_allocation(self):
        """Resolved section should include resource_allocation field."""
        from scripts.ledger_workflow import get_workflow_state_template

        template = get_workflow_state_template()
        assert "resource_allocation:" in template


# =============================================================================
# Test Workflow State Template with Parameters
# =============================================================================

class TestWorkflowStateTemplateWithParams:
    """Tests for generating workflow state template with specific values."""

    def test_template_with_pattern_name(self):
        """Should generate template with specific pattern name."""
        from scripts.ledger_workflow import get_workflow_state_template

        template = get_workflow_state_template(pattern="hierarchical")
        assert "pattern: hierarchical" in template

    def test_template_with_phase_numbers(self):
        """Should generate template with specific phase info."""
        from scripts.ledger_workflow import get_workflow_state_template

        template = get_workflow_state_template(phase=2, total_phases=5)
        assert "phase: 2" in template
        assert "total_phases: 5" in template

    def test_template_with_goal(self):
        """Should generate template with specific goal."""
        from scripts.ledger_workflow import get_workflow_state_template

        template = get_workflow_state_template(goal="implement auth flow")
        assert 'goal: "implement auth flow"' in template

    def test_template_with_resource_allocation(self):
        """Should generate template with resource allocation."""
        from scripts.ledger_workflow import get_workflow_state_template

        template = get_workflow_state_template(resource_allocation="aggressive")
        assert "resource_allocation: aggressive" in template

    def test_template_with_unknowns_list(self):
        """Should generate template with unknowns list."""
        from scripts.ledger_workflow import get_workflow_state_template

        template = get_workflow_state_template(
            unknowns=["auth mechanism UNKNOWN", "rate limit UNKNOWN"]
        )
        assert "auth mechanism UNKNOWN" in template
        assert "rate limit UNKNOWN" in template


# =============================================================================
# Test Parse Workflow State
# =============================================================================

class TestParseWorkflowState:
    """Tests for parsing workflow state from markdown."""

    def test_parse_extracts_pattern(self):
        """Should extract pattern from markdown."""
        from scripts.ledger_workflow import parse_workflow_state

        markdown = """### Workflow State
pattern: swarm
phase: 1
"""
        result = parse_workflow_state(markdown)
        assert result["pattern"] == "swarm"

    def test_parse_extracts_phase(self):
        """Should extract phase as integer."""
        from scripts.ledger_workflow import parse_workflow_state

        markdown = """### Workflow State
pattern: pipeline
phase: 3
total_phases: 7
"""
        result = parse_workflow_state(markdown)
        assert result["phase"] == 3
        assert result["total_phases"] == 7

    def test_parse_extracts_retries(self):
        """Should extract retry counts."""
        from scripts.ledger_workflow import parse_workflow_state

        markdown = """### Workflow State
pattern: hierarchical
retries: 1
max_retries: 3
"""
        result = parse_workflow_state(markdown)
        assert result["retries"] == 1
        assert result["max_retries"] == 3

    def test_parse_extracts_resolved_goal(self):
        """Should extract resolved goal."""
        from scripts.ledger_workflow import parse_workflow_state

        markdown = """### Workflow State
pattern: swarm

#### Resolved
- goal: "build auth system"
- resource_allocation: balanced
"""
        result = parse_workflow_state(markdown)
        assert result["resolved"]["goal"] == "build auth system"

    def test_parse_extracts_unknowns(self):
        """Should extract unknowns list."""
        from scripts.ledger_workflow import parse_workflow_state

        markdown = """### Workflow State
pattern: generator-critic

#### Unknowns
- rate_limit: UNKNOWN
- error_format: UNKNOWN
"""
        result = parse_workflow_state(markdown)
        assert "rate_limit" in result["unknowns"]
        assert "error_format" in result["unknowns"]

    def test_parse_extracts_last_failure(self):
        """Should extract last failure context."""
        from scripts.ledger_workflow import parse_workflow_state

        markdown = """### Workflow State
pattern: jury

#### Last Failure
Build failed: missing dependency xyz
"""
        result = parse_workflow_state(markdown)
        assert "Build failed" in result["last_failure"]

    def test_parse_returns_none_for_missing_section(self):
        """Should return None for missing workflow state."""
        from scripts.ledger_workflow import parse_workflow_state

        markdown = """## Ledger
Just a regular ledger without workflow state.
"""
        result = parse_workflow_state(markdown)
        assert result is None

    def test_parse_handles_empty_unknowns(self):
        """Should handle empty unknowns section."""
        from scripts.ledger_workflow import parse_workflow_state

        markdown = """### Workflow State
pattern: pipeline

#### Resolved
- goal: "done"

#### Unknowns
(none)
"""
        result = parse_workflow_state(markdown)
        assert result["unknowns"] == []


# =============================================================================
# Test Erotetic Integration
# =============================================================================

class TestEroteticIntegration:
    """Tests for erotetic pattern integration with workflow state."""

    def test_check_workflow_readiness_with_unknowns(self):
        """Should return isEmpty=False when unknowns exist."""
        from scripts.ledger_workflow import check_workflow_readiness

        state = {
            "pattern": "swarm",
            "phase": 1,
            "resolved": {"goal": "build feature"},
            "unknowns": ["auth_method", "storage_backend"],
        }

        result = check_workflow_readiness(state)
        assert result["isEmpty"] is False
        assert result["count"] == 2

    def test_check_workflow_readiness_all_resolved(self):
        """Should return isEmpty=True when all resolved."""
        from scripts.ledger_workflow import check_workflow_readiness

        state = {
            "pattern": "hierarchical",
            "phase": 2,
            "resolved": {"goal": "build feature", "auth_method": "JWT"},
            "unknowns": [],
        }

        result = check_workflow_readiness(state)
        assert result["isEmpty"] is True
        assert result["count"] == 0

    def test_check_workflow_readiness_returns_unknowns_list(self):
        """Should return list of unknown names."""
        from scripts.ledger_workflow import check_workflow_readiness

        state = {
            "pattern": "jury",
            "unknowns": ["validation_rules", "error_format"],
        }

        result = check_workflow_readiness(state)
        assert "validation_rules" in result["unknowns"]
        assert "error_format" in result["unknowns"]


# =============================================================================
# Test Codebase Detection - Return Type
# =============================================================================

class TestCodebaseDetectionReturnType:
    """Tests for is_known_codebase return type."""

    def test_returns_boolean(self):
        """is_known_codebase should return a boolean."""
        from scripts.ledger_workflow import is_known_codebase

        with tempfile.TemporaryDirectory() as tmpdir:
            result = is_known_codebase(tmpdir)
            assert isinstance(result, bool)

    def test_returns_false_for_new_codebase(self):
        """Should return False for new codebase (no handoffs)."""
        from scripts.ledger_workflow import is_known_codebase

        with tempfile.TemporaryDirectory() as tmpdir:
            result = is_known_codebase(tmpdir)
            assert result is False

    def test_returns_true_for_known_codebase(self):
        """Should return True when handoffs exist."""
        from scripts.ledger_workflow import is_known_codebase

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create handoffs directory structure
            handoffs_dir = os.path.join(tmpdir, "thoughts", "shared", "handoffs", "test-session")
            os.makedirs(handoffs_dir)

            # Create a handoff file
            handoff_path = os.path.join(handoffs_dir, "current.md")
            with open(handoff_path, "w") as f:
                f.write("# Handoff\n")

            result = is_known_codebase(tmpdir)
            assert result is True


# =============================================================================
# Test Codebase Detection - Directory Checks
# =============================================================================

class TestCodebaseDetectionDirectoryChecks:
    """Tests for codebase detection directory traversal."""

    def test_checks_handoffs_directory(self):
        """Should check thoughts/shared/handoffs/ directory."""
        from scripts.ledger_workflow import is_known_codebase

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create partial path - no handoffs
            partial = os.path.join(tmpdir, "thoughts", "shared")
            os.makedirs(partial)

            result = is_known_codebase(tmpdir)
            assert result is False

    def test_empty_handoffs_dir_returns_false(self):
        """Empty handoffs directory should return False."""
        from scripts.ledger_workflow import is_known_codebase

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create empty handoffs directory
            handoffs_dir = os.path.join(tmpdir, "thoughts", "shared", "handoffs")
            os.makedirs(handoffs_dir)

            result = is_known_codebase(tmpdir)
            assert result is False

    def test_handoffs_with_subdirs_no_files_returns_false(self):
        """Handoffs with empty subdirs should return False."""
        from scripts.ledger_workflow import is_known_codebase

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create handoffs with empty session dir
            session_dir = os.path.join(tmpdir, "thoughts", "shared", "handoffs", "session-1")
            os.makedirs(session_dir)

            result = is_known_codebase(tmpdir)
            assert result is False

    def test_handoffs_with_md_files_returns_true(self):
        """Handoffs with .md files should return True."""
        from scripts.ledger_workflow import is_known_codebase

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create handoff with .md file
            session_dir = os.path.join(tmpdir, "thoughts", "shared", "handoffs", "auth-feature")
            os.makedirs(session_dir)

            with open(os.path.join(session_dir, "current.md"), "w") as f:
                f.write("# Handoff content")

            result = is_known_codebase(tmpdir)
            assert result is True

    def test_multiple_sessions_with_files(self):
        """Multiple session directories with files should return True."""
        from scripts.ledger_workflow import is_known_codebase

        with tempfile.TemporaryDirectory() as tmpdir:
            handoffs_base = os.path.join(tmpdir, "thoughts", "shared", "handoffs")

            # Create multiple sessions
            for name in ["session-1", "session-2", "api-refactor"]:
                session_dir = os.path.join(handoffs_base, name)
                os.makedirs(session_dir)
                with open(os.path.join(session_dir, "current.md"), "w") as f:
                    f.write(f"# {name} handoff")

            result = is_known_codebase(tmpdir)
            assert result is True

    def test_non_md_files_not_counted(self):
        """Non-.md files should not count as handoffs."""
        from scripts.ledger_workflow import is_known_codebase

        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = os.path.join(tmpdir, "thoughts", "shared", "handoffs", "test")
            os.makedirs(session_dir)

            # Create non-.md files
            with open(os.path.join(session_dir, "notes.txt"), "w") as f:
                f.write("just notes")
            with open(os.path.join(session_dir, "data.json"), "w") as f:
                f.write("{}")

            result = is_known_codebase(tmpdir)
            assert result is False

    def test_handles_nonexistent_project_dir(self):
        """Should return False for nonexistent project directory."""
        from scripts.ledger_workflow import is_known_codebase

        result = is_known_codebase("/nonexistent/path/to/project")
        assert result is False


# =============================================================================
# Test SKILL.md Template Update
# =============================================================================

class TestSkillMdTemplate:
    """Tests that SKILL.md includes workflow state template."""

    def test_skill_md_has_workflow_state_section(self):
        """SKILL.md should document Workflow State section."""
        skill_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", ".claude", "skills", "continuity_ledger", "SKILL.md"
        )

        with open(skill_path) as f:
            content = f.read()

        assert "### Workflow State" in content

    def test_skill_md_has_erotetic_fields(self):
        """SKILL.md should document erotetic fields (Resolved, Unknowns)."""
        skill_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", ".claude", "skills", "continuity_ledger", "SKILL.md"
        )

        with open(skill_path) as f:
            content = f.read()

        assert "#### Resolved" in content
        assert "#### Unknowns" in content

    def test_skill_md_has_pattern_field(self):
        """SKILL.md should document pattern field."""
        skill_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", ".claude", "skills", "continuity_ledger", "SKILL.md"
        )

        with open(skill_path) as f:
            content = f.read()

        assert "pattern:" in content

    def test_skill_md_has_phase_fields(self):
        """SKILL.md should document phase and total_phases fields."""
        skill_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", ".claude", "skills", "continuity_ledger", "SKILL.md"
        )

        with open(skill_path) as f:
            content = f.read()

        assert "phase:" in content
        assert "total_phases:" in content

    def test_skill_md_has_retries_fields(self):
        """SKILL.md should document retries and max_retries fields."""
        skill_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", ".claude", "skills", "continuity_ledger", "SKILL.md"
        )

        with open(skill_path) as f:
            content = f.read()

        assert "retries:" in content
        assert "max_retries:" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
