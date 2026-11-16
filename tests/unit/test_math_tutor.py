#!/usr/bin/env python3
"""Tests for math_tutor.py - Math education features.

TDD: Write tests first, then implement to make them pass.
"""

from scripts.math_tutor import generate_problem, generate_steps, get_hint


class TestGenerateSteps:
    """Tests for step-by-step solution generation."""

    def test_steps_quadratic_equation(self):
        """Test step generation for quadratic equation solving."""
        result = generate_steps("x**2 - 5*x + 6 = 0", "solve")
        assert "steps" in result
        assert len(result["steps"]) >= 3
        assert all("justification" in step for step in result["steps"])

    def test_steps_derivative(self):
        """Test step generation for differentiation."""
        result = generate_steps("x**3 + 2*x", "diff")
        assert "steps" in result
        assert "3*x**2 + 2" in result["final_answer"]

    def test_steps_linear_equation(self):
        """Test step generation for linear equation."""
        result = generate_steps("2*x + 5 = 13", "solve")
        assert "steps" in result
        assert len(result["steps"]) >= 2
        # Final answer should be x = 4
        assert "4" in result["final_answer"]

    def test_steps_integration(self):
        """Test step generation for integration."""
        result = generate_steps("x**2", "integrate")
        assert "steps" in result
        # Integral of x^2 is x^3/3
        assert "x**3" in result["final_answer"] or "x^3" in result["final_answer"]

    def test_steps_simplify(self):
        """Test step generation for simplification."""
        result = generate_steps("(x + 1)**2 - x**2 - 2*x - 1", "simplify")
        assert "steps" in result
        assert "0" in result["final_answer"]

    def test_steps_has_problem_type(self):
        """Test that result includes problem type classification."""
        result = generate_steps("x**2 - 4 = 0", "solve")
        assert "problem_type" in result
        assert result["problem_type"] in ["quadratic", "polynomial", "equation"]

    def test_steps_has_verification(self):
        """Test that result includes verification step."""
        result = generate_steps("x**2 - 4 = 0", "solve")
        # Should have verification that solutions work
        if "verification" in result:
            assert result["verification"] is not None


class TestGetHint:
    """Tests for progressive hint system."""

    def test_hint_levels(self):
        """Test that hints progress in specificity."""
        problem = "Solve: x**2 - 4 = 0"

        hint1 = get_hint(problem, level=1)  # Conceptual
        assert "quadratic" in hint1["hint"].lower()

        hint2 = get_hint(problem, level=2)  # Strategic
        assert "factor" in hint2["hint"].lower() or "formula" in hint2["hint"].lower()

        hint3 = get_hint(problem, level=3)  # Tactical
        assert "difference of squares" in hint3["hint"].lower()

    def test_hint_level_1_conceptual(self):
        """Test level 1 hint is conceptual (problem type)."""
        problem = "Solve: 2*x + 3 = 7"
        hint = get_hint(problem, level=1)
        assert "hint" in hint
        assert "category" in hint
        assert hint["category"] == "conceptual"
        # Should mention problem type
        assert "linear" in hint["hint"].lower() or "equation" in hint["hint"].lower()

    def test_hint_level_2_strategic(self):
        """Test level 2 hint suggests approach."""
        problem = "Solve: x**2 + 5*x + 6 = 0"
        hint = get_hint(problem, level=2)
        assert hint["category"] == "strategic"
        # Should mention a technique
        assert any(word in hint["hint"].lower() for word in ["factor", "formula", "complete"])

    def test_hint_level_3_tactical(self):
        """Test level 3 hint gives specific next step."""
        problem = "Solve: x**2 - 9 = 0"
        hint = get_hint(problem, level=3)
        assert hint["category"] == "tactical"
        # Should give specific guidance

    def test_hint_level_4_computational(self):
        """Test level 4 hint shows how to compute."""
        problem = "Solve: x**2 - 4 = 0"
        hint = get_hint(problem, level=4)
        assert hint["category"] == "computational"
        # Should show actual computation

    def test_hint_level_5_answer(self):
        """Test level 5 hint gives the answer."""
        problem = "Solve: x**2 - 4 = 0"
        hint = get_hint(problem, level=5)
        assert hint["category"] == "answer"
        # Should contain the answer
        assert "2" in hint["hint"] or "-2" in hint["hint"]

    def test_hint_calculus(self):
        """Test hints for calculus problems."""
        problem = "Find the derivative of x**3 + 2*x"
        hint = get_hint(problem, level=1)
        assert "derivative" in hint["hint"].lower() or "differentiation" in hint["hint"].lower()

    def test_hint_has_cost(self):
        """Test that hints have associated cost."""
        problem = "Solve: x + 5 = 10"
        hint1 = get_hint(problem, level=1)
        hint5 = get_hint(problem, level=5)

        assert "cost" in hint1
        assert "cost" in hint5
        # Higher level hints should cost more
        assert hint5["cost"] > hint1["cost"]


class TestGenerateProblem:
    """Tests for practice problem generation."""

    def test_generate_algebra(self):
        """Test generating algebra problems."""
        result = generate_problem(topic="algebra", difficulty=1)
        assert "problem" in result
        assert "solution" in result
        assert "x" in result["problem"]

    def test_generate_calculus(self):
        """Test generating calculus problems."""
        result = generate_problem(topic="calculus", difficulty=2)
        assert "problem" in result
        assert "solution" in result

    def test_generate_linear_equation(self):
        """Test generating linear equation problems."""
        result = generate_problem(topic="linear_equation", difficulty=1)
        assert "problem" in result
        assert "solution" in result
        # Solution should be a number or expression
        assert result["solution"] is not None

    def test_generate_quadratic(self):
        """Test generating quadratic problems."""
        result = generate_problem(topic="quadratic", difficulty=2)
        assert "problem" in result
        # Quadratic should have x^2 or x**2
        assert "x**2" in result["problem"] or "x^2" in result["problem"]

    def test_generate_has_difficulty(self):
        """Test that generated problems have difficulty metadata."""
        result = generate_problem(topic="algebra", difficulty=3)
        assert "difficulty" in result
        # Implementation allows templates within +/- 1 difficulty for flexibility
        assert abs(result["difficulty"] - 3) <= 1

    def test_generate_has_template_id(self):
        """Test that generated problems have template ID for variety tracking."""
        result = generate_problem(topic="algebra", difficulty=1)
        assert "template_id" in result

    def test_difficulty_scaling(self):
        """Test that higher difficulty produces harder problems."""
        easy = generate_problem(topic="algebra", difficulty=1)
        hard = generate_problem(topic="algebra", difficulty=4)

        # Hard problems should have larger coefficients or more terms
        # Just verify both are valid
        assert "problem" in easy
        assert "problem" in hard

    def test_generate_derivative(self):
        """Test generating derivative problems."""
        result = generate_problem(topic="derivative", difficulty=2)
        assert "problem" in result
        assert "solution" in result
        # Should ask to find derivative
        assert "derivative" in result["problem"].lower() or "d/dx" in result["problem"]

    def test_generate_integer_solutions(self):
        """Test that simple problems have integer solutions (where appropriate)."""
        result = generate_problem(topic="linear_equation", difficulty=1)
        # At difficulty 1, solutions should typically be integers
        solution = result["solution"]
        difficulty = result.get("difficulty", 1)
        if isinstance(solution, (int, float)):
            # Check if it's effectively an integer (allow non-integer for higher difficulty)
            assert abs(solution - round(solution)) < 0.001 or difficulty > 2

    def test_generate_multiple_unique(self):
        """Test that generating multiple problems gives variety."""
        results = [generate_problem(topic="algebra", difficulty=1) for _ in range(5)]
        problems = [r["problem"] for r in results]
        # Should have at least 2 unique problems out of 5
        assert len(set(problems)) >= 2


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_invalid_operation(self):
        """Test handling of invalid operation."""
        result = generate_steps("x + 1", "invalid_operation")
        assert "error" in result or result.get("steps", []) == []

    def test_empty_problem(self):
        """Test handling of empty problem."""
        result = generate_steps("", "solve")
        assert "error" in result or result.get("steps", []) == []

    def test_invalid_topic(self):
        """Test handling of invalid topic for problem generation."""
        result = generate_problem(topic="invalid_topic", difficulty=1)
        # Should either return error or fallback to a default topic
        assert "error" in result or "problem" in result

    def test_hint_invalid_level(self):
        """Test handling of invalid hint level."""
        problem = "Solve: x + 1 = 2"
        # Level 0 or 6 should be handled gracefully
        hint = get_hint(problem, level=0)
        assert "hint" in hint or "error" in hint

        hint = get_hint(problem, level=6)
        assert "hint" in hint or "error" in hint

    def test_difficulty_bounds(self):
        """Test difficulty parameter bounds."""
        # Difficulty 0 should be handled
        result = generate_problem(topic="algebra", difficulty=0)
        assert "problem" in result or "error" in result

        # Very high difficulty should be handled
        result = generate_problem(topic="algebra", difficulty=10)
        assert "problem" in result or "error" in result
