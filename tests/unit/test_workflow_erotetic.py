"""Phase 1: Erotetic Gate + Display Tests (Python side)

TDD: These tests are written BEFORE implementation.
Run: uv run pytest tests/unit/test_workflow_erotetic.py -v

Tests cover:
1. extractPropositions() - Python wrapper for proposition extraction
2. Erotetic gate integration - Block if missing critical propositions
3. Gate display - Status format for CLI/logging
4. Don Norman feedback - Structured error messages
"""

import pytest
from typing import NamedTuple, Optional
from dataclasses import dataclass


# ============================================================
# Expected Types (TDD - define interface before implementation)
# ============================================================

@dataclass
class Proposition:
    """A single extracted proposition."""
    name: str
    value: str  # Extracted value or "UNKNOWN"
    source: str  # Where it was extracted from (e.g., "prompt", "context")


@dataclass
class ClarificationQuestion:
    """A question to ask the user for unknown propositions."""
    header: str
    proposition: str
    options: list[str]
    why: str


@dataclass
class GateFeedback:
    """Structured feedback for blocked gates (Don Norman principles)."""
    gate: str
    status: str  # 'pass', 'block', 'warn'
    title: str
    details: str
    suggestion: Optional[str] = None


@dataclass
class GateResult:
    """Result of evaluating a gate."""
    decision: str  # 'continue' or 'block'
    unknowns: list[str]
    feedback: Optional[GateFeedback] = None


# ============================================================
# SECTION 1: extract_propositions() Tests
# ============================================================

class TestExtractPropositions:
    """Tests for proposition extraction from user prompts."""

    def test_import_extract_propositions(self):
        """extract_propositions function should be importable."""
        # This will fail until we export from scripts/workflow_erotetic.py
        from scripts.workflow_erotetic import extract_propositions
        assert extract_propositions is not None

    def test_extract_framework_from_prompt(self):
        """Should extract framework from implementation prompt."""
        from scripts.workflow_erotetic import extract_propositions

        prompt = "Build a FastAPI backend with JWT authentication"
        props = extract_propositions(prompt)

        assert props.get("framework") == "fastapi"

    def test_extract_auth_method_from_prompt(self):
        """Should extract auth_method from prompt."""
        from scripts.workflow_erotetic import extract_propositions

        prompt = "Build a FastAPI backend with JWT authentication"
        props = extract_propositions(prompt)

        assert props.get("auth_method") == "jwt"

    def test_extract_multiple_propositions(self):
        """Should extract multiple propositions from complex prompt."""
        from scripts.workflow_erotetic import extract_propositions

        prompt = "Create a Django app with OAuth2 and PostgreSQL on AWS"
        props = extract_propositions(prompt)

        assert props.get("framework") == "django"
        assert props.get("auth_method") == "oauth"
        assert props.get("database") == "postgresql"
        assert props.get("hosting") == "aws"

    def test_mark_missing_as_unknown(self):
        """Missing propositions should be marked as UNKNOWN."""
        from scripts.workflow_erotetic import extract_propositions

        prompt = "Build an API backend"
        props = extract_propositions(prompt)

        assert props.get("framework") == "UNKNOWN"
        assert props.get("auth_method") == "UNKNOWN"
        assert props.get("database") == "UNKNOWN"

    def test_handle_empty_input(self):
        """Empty input should mark all as UNKNOWN."""
        from scripts.workflow_erotetic import extract_propositions

        prompt = ""
        props = extract_propositions(prompt)

        assert props.get("framework") == "UNKNOWN"

    def test_normalize_case(self):
        """Extracted values should be lowercase."""
        from scripts.workflow_erotetic import extract_propositions

        prompt = "Build with FASTAPI and PostgreSQL"
        props = extract_propositions(prompt)

        assert props.get("framework") == "fastapi"
        assert props.get("database") == "postgresql"

    def test_extract_language(self):
        """Should extract programming language."""
        from scripts.workflow_erotetic import extract_propositions

        prompt = "Create a Python service with Flask"
        props = extract_propositions(prompt)

        assert props.get("language") == "python"
        assert props.get("framework") == "flask"


# ============================================================
# SECTION 2: generate_clarification_questions() Tests
# ============================================================

class TestGenerateClarificationQuestions:
    """Tests for generating clarification questions from unknowns."""

    def test_import_generate_questions(self):
        """generate_clarification_questions should be importable."""
        from scripts.workflow_erotetic import generate_clarification_questions
        assert generate_clarification_questions is not None

    def test_generate_questions_for_unknowns(self):
        """Should generate questions for list of unknowns."""
        from scripts.workflow_erotetic import generate_clarification_questions

        unknowns = ["framework", "database"]
        questions = generate_clarification_questions(unknowns)

        assert len(questions) == 2

    def test_question_header_matches_proposition(self):
        """Question header should match proposition name (title case)."""
        from scripts.workflow_erotetic import generate_clarification_questions

        unknowns = ["framework"]
        questions = generate_clarification_questions(unknowns)

        assert questions[0]["header"] == "Framework"
        assert questions[0]["proposition"] == "framework"

    def test_question_has_options(self):
        """Questions should have options for common choices."""
        from scripts.workflow_erotetic import generate_clarification_questions

        unknowns = ["framework"]
        questions = generate_clarification_questions(unknowns)

        assert "FastAPI" in questions[0]["options"]
        assert "Express" in questions[0]["options"]
        assert "Django" in questions[0]["options"]

    def test_question_has_why_explanation(self):
        """Each question should explain why it matters (architectural impact)."""
        from scripts.workflow_erotetic import generate_clarification_questions

        unknowns = ["database"]
        questions = generate_clarification_questions(unknowns)

        assert questions[0]["why"] is not None
        assert len(questions[0]["why"]) > 0
        # Should mention architecture or impact
        why_lower = questions[0]["why"].lower()
        assert any(word in why_lower for word in ["architect", "impact", "choice", "depend"])

    def test_empty_unknowns_returns_empty(self):
        """Empty unknowns list returns empty questions list."""
        from scripts.workflow_erotetic import generate_clarification_questions

        unknowns = []
        questions = generate_clarification_questions(unknowns)

        assert questions == []

    def test_unknown_proposition_handled(self):
        """Unknown proposition types should get default handling."""
        from scripts.workflow_erotetic import generate_clarification_questions

        unknowns = ["custom_unknown_field"]
        questions = generate_clarification_questions(unknowns)

        assert len(questions) == 1
        assert questions[0]["header"] == "Custom Unknown Field"

    def test_questions_ordered_by_q_value(self):
        """Questions should be ordered by architectural impact (Q-value)."""
        from scripts.workflow_erotetic import generate_clarification_questions

        # Framework has higher Q-value than testing
        unknowns = ["testing", "framework", "database"]
        questions = generate_clarification_questions(unknowns)

        props = [q["proposition"] for q in questions]
        framework_idx = props.index("framework")
        testing_idx = props.index("testing")

        assert framework_idx < testing_idx


# ============================================================
# SECTION 3: Gate Display Tests
# ============================================================

class TestGateDisplay:
    """Tests for gate status display formatting."""

    def test_import_format_gate_status(self):
        """format_gate_status should be importable."""
        from scripts.workflow_erotetic import format_gate_status
        assert format_gate_status is not None

    def test_format_all_pending(self):
        """All pending gates should show circles."""
        from scripts.workflow_erotetic import format_gate_status

        status = format_gate_status(
            erotetic="pending",
            resources="pending",
            composition="pending"
        )

        # Should contain E: R: C: in some format
        assert "E:" in status
        assert "R:" in status
        assert "C:" in status

    def test_format_erotetic_passed(self):
        """Passed erotetic gate should show checkmark indicator."""
        from scripts.workflow_erotetic import format_gate_status

        status = format_gate_status(
            erotetic="pass",
            resources="pending",
            composition="pending"
        )

        assert "E:" in status
        # Should have different indicator than pending

    def test_format_blocked_gate(self):
        """Blocked gate should show X indicator."""
        from scripts.workflow_erotetic import format_gate_status

        status = format_gate_status(
            erotetic="block",
            resources="pending",
            composition="pending"
        )

        assert "E:" in status

    def test_single_line_output(self):
        """Status should be single line (for status line display)."""
        from scripts.workflow_erotetic import format_gate_status

        status = format_gate_status(
            erotetic="pass",
            resources="pass",
            composition="pending"
        )

        assert "\n" not in status
        assert len(status) < 30


# ============================================================
# SECTION 4: Erotetic Gate Integration Tests
# ============================================================

class TestErotetticGateIntegration:
    """Tests for evaluating the erotetic gate."""

    def test_import_evaluate_gate(self):
        """evaluate_erotetic_gate should be importable."""
        from scripts.workflow_erotetic import evaluate_erotetic_gate
        assert evaluate_erotetic_gate is not None

    def test_block_when_critical_missing(self):
        """Should block when critical propositions are missing."""
        from scripts.workflow_erotetic import evaluate_erotetic_gate

        prompt = "Build an API"
        result = evaluate_erotetic_gate(prompt)

        assert result["decision"] == "block"
        assert len(result["unknowns"]) > 0

    def test_continue_when_all_present(self):
        """Should continue when all critical propositions are present."""
        from scripts.workflow_erotetic import evaluate_erotetic_gate

        prompt = "Build a FastAPI backend with JWT auth and PostgreSQL"
        result = evaluate_erotetic_gate(prompt)

        assert result["decision"] == "continue"
        assert len(result["unknowns"]) == 0

    def test_continue_for_non_implementation(self):
        """Non-implementation tasks should pass through."""
        from scripts.workflow_erotetic import evaluate_erotetic_gate

        prompt = "Fix the bug in the login function"
        result = evaluate_erotetic_gate(prompt)

        assert result["decision"] == "continue"

    def test_feedback_includes_gate_name(self):
        """Feedback should identify the gate."""
        from scripts.workflow_erotetic import evaluate_erotetic_gate

        prompt = "Build a web app"
        result = evaluate_erotetic_gate(prompt)

        assert result.get("feedback") is not None
        assert result["feedback"]["gate"] == "Erotetic"

    def test_framework_is_critical(self):
        """Framework should be a critical unknown."""
        from scripts.workflow_erotetic import evaluate_erotetic_gate

        prompt = "Build a backend with JWT authentication"
        result = evaluate_erotetic_gate(prompt)

        assert "framework" in result["unknowns"]

    def test_testing_not_critical(self):
        """Testing is not critical for gate pass."""
        from scripts.workflow_erotetic import evaluate_erotetic_gate

        # Prompt has all critical props but no testing framework
        prompt = "Build a FastAPI backend with JWT and PostgreSQL"
        result = evaluate_erotetic_gate(prompt)

        assert result["decision"] == "continue"


# ============================================================
# SECTION 5: Don Norman Feedback Tests
# ============================================================

class TestDonNormanFeedback:
    """Tests for structured error feedback (Don Norman principles)."""

    def test_import_generate_feedback(self):
        """generate_block_feedback should be importable."""
        from scripts.workflow_erotetic import generate_block_feedback
        assert generate_block_feedback is not None

    def test_feedback_has_gate_name(self):
        """Feedback should include gate name."""
        from scripts.workflow_erotetic import generate_block_feedback

        feedback = generate_block_feedback("Erotetic", ["framework"])

        assert feedback["gate"] == "Erotetic"

    def test_feedback_has_actionable_title(self):
        """Feedback should have actionable title."""
        from scripts.workflow_erotetic import generate_block_feedback

        feedback = generate_block_feedback("Erotetic", ["framework", "database"])

        assert feedback["title"] is not None
        assert len(feedback["title"]) > 0
        # Title should mention what needs resolution
        title_lower = feedback["title"].lower()
        assert any(word in title_lower for word in ["missing", "unknown", "clarif", "resolv"])

    def test_feedback_has_details(self):
        """Feedback should include detailed explanation."""
        from scripts.workflow_erotetic import generate_block_feedback

        feedback = generate_block_feedback("Erotetic", ["framework"])

        assert feedback["details"] is not None
        assert "framework" in feedback["details"]

    def test_feedback_has_suggestion(self):
        """Feedback should include suggestion for resolution."""
        from scripts.workflow_erotetic import generate_block_feedback

        feedback = generate_block_feedback("Erotetic", ["database"])

        assert feedback.get("suggestion") is not None
        suggestion_lower = feedback["suggestion"].lower()
        assert any(word in suggestion_lower for word in ["specify", "choose", "select", "ask"])

    def test_feedback_for_multiple_unknowns(self):
        """Feedback should list all unknowns."""
        from scripts.workflow_erotetic import generate_block_feedback

        feedback = generate_block_feedback("Erotetic", ["framework", "auth_method", "database"])

        assert "framework" in feedback["details"]
        assert "auth_method" in feedback["details"]
        assert "database" in feedback["details"]

    def test_feedback_for_empty_unknowns(self):
        """Empty unknowns should still produce valid feedback."""
        from scripts.workflow_erotetic import generate_block_feedback

        feedback = generate_block_feedback("Erotetic", [])

        assert feedback["status"] == "block"
        assert feedback["details"] is not None


# ============================================================
# SECTION 6: Edge Cases
# ============================================================

class TestEdgeCases:
    """Edge case tests for robustness."""

    def test_whitespace_only_input(self):
        """Whitespace-only input should mark all as UNKNOWN."""
        from scripts.workflow_erotetic import extract_propositions

        prompt = "   \n\t  "
        props = extract_propositions(prompt)

        assert props.get("framework") == "UNKNOWN"

    def test_very_long_prompt(self):
        """Very long prompts should still extract correctly."""
        from scripts.workflow_erotetic import extract_propositions

        long_prompt = "Build a FastAPI backend with JWT authentication. " * 100
        props = extract_propositions(long_prompt)

        assert props.get("framework") == "fastapi"

    def test_special_characters(self):
        """Special characters should not break extraction."""
        from scripts.workflow_erotetic import extract_propositions

        prompt = "Build a FastAPI backend with JWT! It's awesome? Yes, indeed."
        props = extract_propositions(prompt)

        assert props.get("framework") == "fastapi"
        assert props.get("auth_method") == "jwt"

    def test_unicode_in_prompt(self):
        """Unicode characters should not break extraction."""
        from scripts.workflow_erotetic import extract_propositions

        prompt = "Build a FastAPI backend - great solution"
        props = extract_propositions(prompt)

        assert props.get("framework") == "fastapi"

    def test_mixed_case_frameworks(self):
        """Mixed case framework names should normalize."""
        from scripts.workflow_erotetic import extract_propositions

        prompt = "Build with NestJS and PostgreSQL"
        props = extract_propositions(prompt)

        assert props.get("framework") == "nestjs"


# ============================================================
# SECTION 7: Integration with z3_erotetic CLI
# ============================================================

class TestZ3ErotetticIntegration:
    """Tests for integration with z3_erotetic_cli.py."""

    def test_call_z3_erotetic_cli(self):
        """Should be able to call z3_erotetic_cli for evocation check."""
        from scripts.workflow_erotetic import call_z3_erotetic

        props = {"framework": "fastapi", "auth_method": "UNKNOWN", "database": "UNKNOWN"}
        result = call_z3_erotetic(props)

        assert "isEmpty" in result
        assert "unknowns" in result

    def test_z3_returns_empty_when_all_known(self):
        """E(X,Q) should be empty when all props are known."""
        from scripts.workflow_erotetic import call_z3_erotetic

        props = {"framework": "fastapi", "auth_method": "jwt", "database": "postgresql"}
        result = call_z3_erotetic(props)

        assert result["isEmpty"] is True
        assert result["unknowns"] == []

    def test_z3_returns_unknowns_list(self):
        """E(X,Q) should list unknowns when present."""
        from scripts.workflow_erotetic import call_z3_erotetic

        props = {"framework": "UNKNOWN", "auth_method": "jwt", "database": "UNKNOWN"}
        result = call_z3_erotetic(props)

        assert result["isEmpty"] is False
        assert "framework" in result["unknowns"]
        assert "database" in result["unknowns"]
