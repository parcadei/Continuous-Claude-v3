#!/usr/bin/env python3
"""Tests for z3_solve.py - Constraint solving cognitive prosthetics.

TDD: These tests written FIRST, before implementation.
"""

import pytest
import sys
from pathlib import Path

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


class TestCheckSat:
    """Tests for check_sat function."""

    def test_sat_simple(self):
        """x > 0, x < 10 should be SAT with valid model."""
        from z3_solve import check_sat

        result = check_sat(["x > 0", "x < 10"], ["x"], "int")
        assert result["satisfiable"] is True
        assert "x" in result["model"]
        x = int(result["model"]["x"])
        assert x > 0
        assert x < 10

    def test_unsat(self):
        """x > 10, x < 5 should be UNSAT."""
        from z3_solve import check_sat

        result = check_sat(["x > 10", "x < 5"], ["x"], "int")
        assert result["satisfiable"] is False
        assert result["model"] is None

    def test_sat_system(self):
        """x + y == 10, x - y == 2 should have solution x=6, y=4."""
        from z3_solve import check_sat

        result = check_sat(["x + y == 10", "x - y == 2"], ["x", "y"], "int")
        assert result["satisfiable"] is True
        x = int(result["model"]["x"])
        y = int(result["model"]["y"])
        assert x + y == 10
        assert x - y == 2

    def test_sat_perfect_square(self):
        """x*x == 49, x > 0 should yield x = 7."""
        from z3_solve import check_sat

        result = check_sat(["x * x == 49", "x > 0"], ["x"], "int")
        assert result["satisfiable"] is True
        assert int(result["model"]["x"]) == 7


class TestProveTheorem:
    """Tests for prove_theorem function."""

    def test_prove_commutativity(self):
        """x + y == y + x should be provable."""
        from z3_solve import prove_theorem

        result = prove_theorem("x + y == y + x", None, ["x", "y"], "int")
        assert result["proved"] is True
        assert result["counterexample"] is None

    def test_prove_false_statement(self):
        """x + 1 == x should NOT be provable (counterexample exists)."""
        from z3_solve import prove_theorem

        result = prove_theorem("x + 1 == x", None, ["x"], "int")
        assert result["proved"] is False
        assert result["counterexample"] is not None

    def test_prove_with_assumption(self):
        """x >= 0 implies x*x >= 0 should be provable."""
        from z3_solve import prove_theorem

        result = prove_theorem("x * x >= 0", ["x >= 0"], ["x"], "real")
        assert result["proved"] is True

    def test_prove_associativity(self):
        """(x + y) + z == x + (y + z) should be provable."""
        from z3_solve import prove_theorem

        result = prove_theorem("(x + y) + z == x + (y + z)", None, ["x", "y", "z"], "int")
        assert result["proved"] is True


class TestOptimize:
    """Tests for optimize function."""

    def test_optimize_maximize(self):
        """Maximize x + y subject to x >= 0, y >= 0, x + y <= 10."""
        from z3_solve import optimize

        result = optimize(
            "x + y",
            ["x >= 0", "y >= 0", "x + y <= 10"],
            ["x", "y"],
            "real",
            "maximize"
        )
        assert result["optimal"] is True
        # Maximum is 10
        assert float(result["value"]) == 10.0

    def test_optimize_minimize(self):
        """Minimize x + y subject to x >= 0, y >= 0, x + y >= 5."""
        from z3_solve import optimize

        result = optimize(
            "x + y",
            ["x >= 0", "y >= 0", "x + y >= 5"],
            ["x", "y"],
            "real",
            "minimize"
        )
        assert result["optimal"] is True
        # Minimum is 5
        assert float(result["value"]) == 5.0

    def test_optimize_infeasible(self):
        """Infeasible constraints should return optimal=False."""
        from z3_solve import optimize

        result = optimize(
            "x",
            ["x > 10", "x < 5"],
            ["x"],
            "real",
            "minimize"
        )
        assert result["optimal"] is False


class TestAutoExtractVariables:
    """Tests for automatic variable extraction."""

    def test_extract_single_var(self):
        """Should extract 'x' from constraint 'x > 0'."""
        from z3_solve import _extract_variables

        vars = _extract_variables(["x > 0"])
        assert "x" in vars

    def test_extract_multiple_vars(self):
        """Should extract 'x', 'y', 'z' from constraints."""
        from z3_solve import _extract_variables

        vars = _extract_variables(["x + y == 10", "y + z == 20"])
        assert set(vars) == {"x", "y", "z"}

    def test_filter_keywords(self):
        """Should NOT include keywords like 'And', 'Or', 'Not'."""
        from z3_solve import _extract_variables

        vars = _extract_variables(["And(x > 0, y > 0)"])
        assert "And" not in vars
        assert "x" in vars
        assert "y" in vars


class TestCreateVariables:
    """Tests for create_variables function."""

    def test_create_int_vars(self):
        """Should create integer Z3 variables."""
        from z3_solve import create_variables
        import z3

        vars = create_variables(["x", "y"], "int")
        assert "x" in vars
        assert "y" in vars
        assert vars["x"].is_int()

    def test_create_real_vars(self):
        """Should create real Z3 variables."""
        from z3_solve import create_variables
        import z3

        vars = create_variables(["x"], "real")
        assert vars["x"].is_real()

    def test_create_typed_vars(self):
        """Should handle type annotation like 'x:real'."""
        from z3_solve import create_variables
        import z3

        vars = create_variables(["x:real", "y:int"], "int")
        assert vars["x"].is_real()
        assert vars["y"].is_int()


class TestParseConstraint:
    """Tests for parse_constraint function."""

    def test_parse_simple_inequality(self):
        """Should parse 'x > 0'."""
        from z3_solve import parse_constraint, create_variables
        import z3

        vars = create_variables(["x"], "int")
        constraint = parse_constraint("x > 0", vars)
        assert constraint is not None

    def test_parse_equality(self):
        """Should parse 'x + y == 10'."""
        from z3_solve import parse_constraint, create_variables
        import z3

        vars = create_variables(["x", "y"], "int")
        constraint = parse_constraint("x + y == 10", vars)
        assert constraint is not None

    def test_parse_invalid(self):
        """Should raise ValueError for invalid constraint."""
        from z3_solve import parse_constraint, create_variables
        import z3

        vars = create_variables(["x"], "int")
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_constraint("x +* y", vars)


class TestCLI:
    """Tests for CLI interface."""

    def test_parse_args_sat(self):
        """Parse args for sat command."""
        from z3_solve import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["z3_solve.py", "sat", "x > 0, x < 10", "--type", "int"]
        try:
            args = parse_args()
            assert args.command == "sat"
            assert args.constraints == "x > 0, x < 10"
            assert args.var_type == "int"
        finally:
            sys.argv = old_argv

    def test_parse_args_prove(self):
        """Parse args for prove command."""
        from z3_solve import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["z3_solve.py", "prove", "x + y == y + x", "--vars", "x", "y"]
        try:
            args = parse_args()
            assert args.command == "prove"
            assert args.theorem == "x + y == y + x"
            assert args.vars == ["x", "y"]
        finally:
            sys.argv = old_argv
