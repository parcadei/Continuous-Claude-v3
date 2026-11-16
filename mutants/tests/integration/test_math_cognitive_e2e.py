#!/usr/bin/env python3
"""Integration tests for Math Cognitive Prosthetics.

TDD: These tests written FIRST, before implementation.

Tests CLI execution via subprocess, error propagation, and tool chaining.
These tests verify the complete pipeline from CLI args to JSON output.

Test classes:
- TestSymPyCLI: E2E tests for sympy_compute.py CLI
- TestZ3CLI: E2E tests for z3_solve.py CLI
- TestMathScratchpadCLI: E2E tests for math_scratchpad.py CLI
- TestErrorPropagation: Error handling tests
- TestToolChaining: SymPy -> Z3 workflow tests
"""

import json
import subprocess
import pytest
from pathlib import Path


PROJECT_DIR = Path(__file__).parent.parent.parent


class TestSymPyCLI:
    """E2E tests for sympy_compute.py CLI.

    These tests run the actual CLI via subprocess and verify JSON output.
    """

    def test_cli_solve_equation(self):
        """CLI solve command should return valid JSON with solutions.

        x^2 - 4 = 0 has solutions x = 2 and x = -2.
        """
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/sympy_compute.py", "solve", "x**2 - 4 = 0",
             "--var", "x", "--domain", "real"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert "solutions" in output
        assert set(output["solutions"]) == {"-2", "2"}

    def test_cli_integrate(self):
        """CLI integrate command should return the integral.

        Integral of x^2 is x^3/3.
        """
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/sympy_compute.py", "integrate", "x**2",
             "--var", "x"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert "result" in output
        assert "x**3/3" in output["result"]

    def test_cli_differentiate(self):
        """CLI diff command should return the derivative.

        d/dx(x^3) = 3*x^2.
        """
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/sympy_compute.py", "diff", "x**3",
             "--var", "x"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert "result" in output
        assert "3*x**2" in output["result"] or "3x**2" in output["result"]

    def test_cli_simplify(self):
        """CLI simplify command should simplify expression.

        sin^2(x) + cos^2(x) simplifies to 1.
        """
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/sympy_compute.py", "simplify", "sin(x)**2 + cos(x)**2",
             "--strategy", "trig"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert "simplified" in output
        assert output["simplified"] == "1"

    def test_cli_definite_integral(self):
        """CLI integrate with bounds should compute definite integral.

        Integral of x from 0 to 1 is 1/2.
        """
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/sympy_compute.py", "integrate", "x",
             "--var", "x", "--bounds", "0", "1"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["definite"] is True
        assert output["result"] == "1/2"


class TestZ3CLI:
    """E2E tests for z3_solve.py CLI.

    These tests run the actual CLI via subprocess and verify JSON output.
    """

    def test_cli_sat(self):
        """CLI sat command should return SAT result with model.

        x > 0, x < 10 is satisfiable.
        """
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/z3_solve.py", "sat", "x > 0, x < 10",
             "--type", "int"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["satisfiable"] is True
        assert "x" in output["model"]
        x = int(output["model"]["x"])
        assert 0 < x < 10

    def test_cli_prove(self):
        """CLI prove command should prove a theorem.

        x + y == y + x (commutativity) is a theorem.
        """
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/z3_solve.py", "prove", "x + y == y + x",
             "--vars", "x", "y", "--type", "int"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["proved"] is True

    def test_cli_optimize_maximize(self):
        """CLI optimize command should find maximum.

        Maximize x + y subject to x + y <= 10, x >= 0, y >= 0.
        Maximum is 10.
        """
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/z3_solve.py", "optimize", "x + y",
             "--constraints", "x >= 0, y >= 0, x + y <= 10",
             "--direction", "maximize", "--type", "real"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["optimal"] is True
        assert float(output["value"]) == 10.0

    def test_cli_unsat(self):
        """CLI sat command should detect unsatisfiable constraints.

        x > 10, x < 5 is unsatisfiable.
        """
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/z3_solve.py", "sat", "x > 10, x < 5",
             "--type", "int"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["satisfiable"] is False


class TestMathScratchpadCLI:
    """E2E tests for math_scratchpad.py CLI.

    These tests run the actual CLI via subprocess and verify JSON output.
    Tests will fail until math_scratchpad.py is implemented.
    """

    def test_cli_verify_step(self):
        """CLI verify command should verify a mathematical claim.

        x = 2 implies x^2 = 4 should be verified as True.
        """
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/math_scratchpad.py", "verify",
             "x = 2 implies x^2 = 4"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["verified"] is True
        assert output["method"] in ["sympy", "z3"]

    def test_cli_verify_with_context(self):
        """CLI verify command with --context should use provided values."""
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/math_scratchpad.py", "verify",
             "x^2 = 4", "--context", '{"x": 2}'],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["verified"] is True

    def test_cli_chain(self):
        """CLI chain command should verify multiple steps.

        All steps in this chain are mathematically valid.
        """
        steps = '["x = 2", "x^2 = 4"]'
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/math_scratchpad.py", "chain",
             "--steps", steps],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["all_valid"] is True
        assert len(output["steps"]) == 2

    def test_cli_chain_with_error(self):
        """CLI chain command should detect first invalid step."""
        steps = '["x = 2", "x^2 = 5"]'  # Error: should be 4
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/math_scratchpad.py", "chain",
             "--steps", steps],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["all_valid"] is False
        assert output["first_error"]["step_index"] == 1

    def test_cli_explain(self):
        """CLI explain command should explain a mathematical step."""
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/math_scratchpad.py", "explain",
             "d/dx(x^3) = 3*x^2"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["operation"] == "differentiation"
        assert "power rule" in output["explanation"].lower()


class TestErrorPropagation:
    """Tests for error handling across tools.

    Verifies that errors are properly propagated and return meaningful messages.
    """

    def test_sympy_invalid_expression(self):
        """Invalid SymPy expression should return error.

        x +* y is not a valid expression.
        """
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/sympy_compute.py", "solve", "x +* y",
             "--var", "x"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        # Should either exit non-zero or return JSON with error
        if result.returncode == 0:
            output = json.loads(result.stdout)
            assert "error" in output or output.get("solutions") == []
        else:
            # Error message should be in stderr or stdout
            combined = result.stderr + result.stdout
            assert "error" in combined.lower() or "invalid" in combined.lower()

    def test_z3_invalid_constraint(self):
        """Invalid Z3 constraint should return error.

        x +* y is not a valid constraint.
        """
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/z3_solve.py", "sat", "x +* y",
             "--type", "int"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        # Should either exit non-zero or return JSON with error
        if result.returncode == 0:
            output = json.loads(result.stdout)
            assert "error" in output
        else:
            combined = result.stderr + result.stdout
            assert "error" in combined.lower() or "parse" in combined.lower()

    def test_scratchpad_empty_chain(self):
        """Empty chain should return all_valid True, not an error."""
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/math_scratchpad.py", "chain",
             "--steps", "[]"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["all_valid"] is True

    def test_sympy_missing_var(self):
        """Missing --var for solve should handle gracefully.

        If no variable specified, should default to 'x' or error cleanly.
        """
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/sympy_compute.py", "solve", "x**2 - 4 = 0"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        # Should either succeed with default var or fail gracefully
        if result.returncode == 0:
            output = json.loads(result.stdout)
            assert "solutions" in output or "error" in output
        else:
            # Should not crash - return helpful error
            assert result.stderr != "" or result.stdout != ""


class TestToolChaining:
    """Tests for chaining SymPy and Z3 together.

    These tests verify that results from one tool can be used as input to another.
    """

    def test_sympy_solve_then_z3_verify(self):
        """Solve with SymPy, then verify each solution with Z3.

        1. Solve x^2 - 4 = 0 with SymPy -> solutions: [-2, 2]
        2. Verify x = 2 satisfies x*x = 4 with Z3
        3. Verify x = -2 satisfies x*x = 4 with Z3
        """
        # Step 1: Solve with SymPy
        solve_result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/sympy_compute.py", "solve", "x**2 - 4 = 0",
             "--var", "x", "--domain", "real"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert solve_result.returncode == 0
        solutions = json.loads(solve_result.stdout)["solutions"]
        assert set(solutions) == {"-2", "2"}

        # Step 2: Verify each solution with Z3
        for sol in solutions:
            prove_result = subprocess.run(
                ["uv", "run", "python", "-m", "runtime.harness",
                 "scripts/z3_solve.py", "sat",
                 f"x == {sol}, x * x == 4",
                 "--type", "int"],
                capture_output=True,
                text=True,
                cwd=PROJECT_DIR,
                timeout=30
            )
            assert prove_result.returncode == 0
            output = json.loads(prove_result.stdout)
            assert output["satisfiable"] is True

    def test_chain_simplify_then_prove(self):
        """Simplify with SymPy, then prove identity with Z3.

        1. Simplify (x+1)^2 - x^2 - 2*x - 1 -> 0
        2. Prove (x+1)^2 == x^2 + 2*x + 1 is a theorem
        """
        # Step 1: Simplify
        simplify_result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/sympy_compute.py", "simplify",
             "(x + 1)**2 - x**2 - 2*x - 1", "--strategy", "auto"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert simplify_result.returncode == 0
        simplified = json.loads(simplify_result.stdout)["simplified"]
        assert simplified == "0"

        # Step 2: Prove the identity
        prove_result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/z3_solve.py", "prove",
             "(x + 1)**2 == x**2 + 2*x + 1",
             "--vars", "x", "--type", "int"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert prove_result.returncode == 0
        assert json.loads(prove_result.stdout)["proved"] is True

    def test_scratchpad_uses_sympy_and_z3(self):
        """Math scratchpad should use both SymPy and Z3 internally.

        Verify a step that requires algebraic verification,
        then verify a step that requires Z3 proof.
        """
        # Step 1: Algebraic claim (uses SymPy)
        result1 = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/math_scratchpad.py", "verify",
             "sin(x)**2 + cos(x)**2 = 1"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result1.returncode == 0
        output1 = json.loads(result1.stdout)
        assert output1["verified"] is True
        assert output1["method"] == "sympy"

        # Step 2: Universal claim (may use Z3)
        result2 = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/math_scratchpad.py", "verify",
             "x + y = y + x"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result2.returncode == 0
        output2 = json.loads(result2.stdout)
        assert output2["verified"] is True
        # Could use either SymPy or Z3 for this

    def test_chain_verification_uses_context(self):
        """Chain verification should propagate context between steps.

        1. x = 3 (establishes context)
        2. y = x + 2 (uses x from context)
        3. x + y = 8 (verifies both)
        """
        steps = '["x = 3", "y = x + 2", "x + y = 8"]'
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/math_scratchpad.py", "chain",
             "--steps", steps],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["all_valid"] is True
        assert len(output["steps"]) == 3

    def test_differentiate_then_verify(self):
        """Differentiate with SymPy, then verify result with scratchpad.

        1. Compute d/dx(x^3) = 3*x^2 with SymPy
        2. Verify this derivation with scratchpad
        """
        # Step 1: Differentiate
        diff_result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/sympy_compute.py", "diff", "x**3",
             "--var", "x"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert diff_result.returncode == 0
        derivative = json.loads(diff_result.stdout)["result"]
        assert "3*x**2" in derivative

        # Step 2: Verify the derivation
        verify_result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/math_scratchpad.py", "verify",
             f"d/dx(x^3) = {derivative}"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert verify_result.returncode == 0
        output = json.loads(verify_result.stdout)
        assert output["verified"] is True


class TestRobustness:
    """Tests for robustness and edge cases."""

    @pytest.mark.slow
    def test_sympy_complex_equation(self):
        """Test with a more complex equation.

        x^4 - 5*x^2 + 4 = 0 should have 4 solutions.
        """
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/sympy_compute.py", "solve", "x**4 - 5*x**2 + 4 = 0",
             "--var", "x", "--domain", "real"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=60
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert len(output["solutions"]) == 4

    def test_z3_with_real_vars(self):
        """Test Z3 with real-valued variables."""
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/z3_solve.py", "sat", "x > 0, x < 1",
             "--type", "real"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["satisfiable"] is True
        # Z3 returns rationals like "1/2" - parse them
        x_str = output["model"]["x"].replace("?", "")
        if "/" in x_str:
            num, denom = x_str.split("/")
            x = float(num) / float(denom)
        else:
            x = float(x_str)
        assert 0 < x < 1

    def test_unicode_in_expression(self):
        """Test handling of Unicode mathematical symbols.

        Some users might input Unicode symbols like pi, sqrt.
        """
        result = subprocess.run(
            ["uv", "run", "python", "-m", "runtime.harness",
             "scripts/sympy_compute.py", "simplify", "pi + 0"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=30
        )
        # Should either handle pi or reject gracefully
        assert result.returncode == 0 or "error" in result.stderr.lower()
