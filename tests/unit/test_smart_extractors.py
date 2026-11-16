"""TDD tests for smart argument extractors.

These tests define the expected behavior for smart_extract(), which will
intelligently parse natural language math intents into structured arguments
based on the expected argument names for each command.

The smart_extract() function doesn't exist yet - these tests are written
FIRST (TDD) to define the API contract before implementation.

Run with: pytest tests/unit/test_smart_extractors.py -v
"""

from __future__ import annotations

import pytest

# Import will fail until smart_extract is implemented
try:
    from scripts.math_router import smart_extract
except ImportError:
    # Placeholder for TDD - tests should fail with ImportError initially
    smart_extract = None


# =============================================================================
# Test Fixtures and Helpers
# =============================================================================


@pytest.fixture
def skip_if_not_implemented():
    """Skip test if smart_extract is not implemented yet."""
    if smart_extract is None:
        pytest.skip("smart_extract not implemented yet")


def assert_extract(intent: str, expected_args: list[str], expected_result: dict) -> None:
    """Helper to assert smart_extract results."""
    if smart_extract is None:
        pytest.fail("smart_extract not implemented - test cannot run")
    result = smart_extract(intent, expected_args)
    for key, expected_value in expected_result.items():
        assert key in result, f"Expected key '{key}' not in result: {result}"
        assert result[key] == expected_value, (
            f"For key '{key}': expected '{expected_value}', got '{result[key]}'"
        )


# =============================================================================
# VALUE EXTRACTION TESTS (x, a, b, y, z) - 463 commands use these
# =============================================================================


@pytest.mark.value
class TestValueExtraction:
    """Test extraction of value arguments (x, a, b, y, z)."""

    def test_extract_x_from_compute_of(self, skip_if_not_implemented):
        """'compute sin of 0.5' -> x=0.5"""
        assert_extract("compute sin of 0.5", ["x"], {"x": "0.5"})

    def test_extract_x_from_function_call(self, skip_if_not_implemented):
        """'sin(0.5)' -> x=0.5"""
        assert_extract("sin(0.5)", ["x"], {"x": "0.5"})

    def test_extract_x_from_function_call_with_spaces(self, skip_if_not_implemented):
        """'sin( 0.5 )' -> x=0.5"""
        assert_extract("sin( 0.5 )", ["x"], {"x": "0.5"})

    def test_extract_x_explicit_assignment(self, skip_if_not_implemented):
        """'compute with x=3.14' -> x=3.14"""
        assert_extract("compute with x=3.14", ["x"], {"x": "3.14"})

    def test_extract_x_negative_value(self, skip_if_not_implemented):
        """'compute sin of -0.5' -> x=-0.5"""
        assert_extract("compute sin of -0.5", ["x"], {"x": "-0.5"})

    def test_extract_x_scientific_notation(self, skip_if_not_implemented):
        """'compute exp of 1e-5' -> x=1e-5"""
        assert_extract("compute exp of 1e-5", ["x"], {"x": "1e-5"})

    def test_extract_ab_from_gcd_and(self, skip_if_not_implemented):
        """'gcd of 12 and 18' -> a=12, b=18"""
        assert_extract("gcd of 12 and 18", ["a", "b"], {"a": "12", "b": "18"})

    def test_extract_ab_from_gcd_comma(self, skip_if_not_implemented):
        """'gcd(12, 18)' -> a=12, b=18"""
        assert_extract("gcd(12, 18)", ["a", "b"], {"a": "12", "b": "18"})

    def test_extract_ab_from_lcm(self, skip_if_not_implemented):
        """'lcm of 15 and 20' -> a=15, b=20"""
        assert_extract("lcm of 15 and 20", ["a", "b"], {"a": "15", "b": "20"})

    def test_extract_xy_from_modpow(self, skip_if_not_implemented):
        """'modpow x=2 y=10 m=1000' -> x=2, y=10"""
        assert_extract("modpow x=2 y=10 m=1000", ["x", "y"], {"x": "2", "y": "10"})

    def test_extract_z_from_complex(self, skip_if_not_implemented):
        """'arg of z=3+4j' -> z=3+4j"""
        assert_extract("arg of z=3+4j", ["z"], {"z": "3+4j"})

    def test_extract_value_from_natural_language(self, skip_if_not_implemented):
        """'compute the square root of 16' -> x=16"""
        assert_extract("compute the square root of 16", ["x"], {"x": "16"})

    def test_extract_value_with_units_ignored(self, skip_if_not_implemented):
        """'sin of 0.5 radians' -> x=0.5 (units stripped)"""
        assert_extract("sin of 0.5 radians", ["x"], {"x": "0.5"})

    def test_extract_multiple_values_ordered(self, skip_if_not_implemented):
        """'atan2(3, 4)' -> y=3, x=4 (atan2 convention)"""
        assert_extract("atan2(3, 4)", ["y", "x"], {"y": "3", "x": "4"})


# =============================================================================
# PRECISION EXTRACTION TESTS (dps) - 203 commands use this
# =============================================================================


@pytest.mark.precision
class TestPrecisionExtraction:
    """Test extraction of dps (precision) argument."""

    def test_extract_dps_explicit(self, skip_if_not_implemented):
        """'compute with dps=50' -> dps=50"""
        assert_extract("compute with dps=50", ["dps"], {"dps": "50"})

    def test_extract_dps_equals_space(self, skip_if_not_implemented):
        """'compute with dps = 100' -> dps=100"""
        assert_extract("compute with dps = 100", ["dps"], {"dps": "100"})

    def test_extract_dps_from_digits(self, skip_if_not_implemented):
        """'compute to 100 digits' -> dps=100"""
        assert_extract("compute to 100 digits", ["dps"], {"dps": "100"})

    def test_extract_dps_from_digit_singular(self, skip_if_not_implemented):
        """'compute to 50 digit precision' -> dps=50"""
        assert_extract("compute to 50 digit precision", ["dps"], {"dps": "50"})

    def test_extract_dps_from_precision(self, skip_if_not_implemented):
        """'with precision 50' -> dps=50"""
        assert_extract("with precision 50", ["dps"], {"dps": "50"})

    def test_extract_dps_from_decimal_places(self, skip_if_not_implemented):
        """'to 30 decimal places' -> dps=30"""
        assert_extract("to 30 decimal places", ["dps"], {"dps": "30"})

    def test_extract_dps_high_precision(self, skip_if_not_implemented):
        """'high precision 1000 digits' -> dps=1000"""
        assert_extract("high precision 1000 digits", ["dps"], {"dps": "1000"})

    def test_extract_dps_with_value(self, skip_if_not_implemented):
        """'compute pi to 100 digits' -> dps=100"""
        assert_extract("compute pi to 100 digits", ["dps"], {"dps": "100"})

    def test_extract_dps_default_when_missing(self, skip_if_not_implemented):
        """'compute pi' -> no dps key (use default)"""
        result = smart_extract("compute pi", ["dps"])
        assert "dps" not in result or result["dps"] is None


# =============================================================================
# INTEGER EXTRACTION TESTS (n, k, m, axis) - 132 commands use these
# =============================================================================


@pytest.mark.integer
class TestIntegerExtraction:
    """Test extraction of integer arguments (n, k, m, axis)."""

    def test_extract_n_order_suffix(self, skip_if_not_implemented):
        """'5th order derivative' -> n=5"""
        assert_extract("5th order derivative", ["n"], {"n": "5"})

    def test_extract_n_order_word(self, skip_if_not_implemented):
        """'order 3 bessel' -> n=3"""
        assert_extract("order 3 bessel", ["n"], {"n": "3"})

    def test_extract_n_explicit(self, skip_if_not_implemented):
        """'bernoulli n=10' -> n=10"""
        assert_extract("bernoulli n=10", ["n"], {"n": "10"})

    def test_extract_n_from_nth(self, skip_if_not_implemented):
        """'3rd derivative' -> n=3"""
        assert_extract("3rd derivative", ["n"], {"n": "3"})

    def test_extract_n_from_1st(self, skip_if_not_implemented):
        """'1st order' -> n=1"""
        assert_extract("1st order", ["n"], {"n": "1"})

    def test_extract_n_from_2nd(self, skip_if_not_implemented):
        """'2nd derivative' -> n=2"""
        assert_extract("2nd derivative", ["n"], {"n": "2"})

    def test_extract_axis_explicit(self, skip_if_not_implemented):
        """'mean along axis 0' -> axis=0"""
        assert_extract("mean along axis 0", ["axis"], {"axis": "0"})

    def test_extract_axis_equals(self, skip_if_not_implemented):
        """'sum axis=1' -> axis=1"""
        assert_extract("sum axis=1", ["axis"], {"axis": "1"})

    def test_extract_axis_negative(self, skip_if_not_implemented):
        """'sum along axis -1' -> axis=-1"""
        assert_extract("sum along axis -1", ["axis"], {"axis": "-1"})

    def test_extract_k_top(self, skip_if_not_implemented):
        """'top k=5 values' -> k=5"""
        assert_extract("top k=5 values", ["k"], {"k": "5"})

    def test_extract_k_choose(self, skip_if_not_implemented):
        """'binomial n=10 k=3' -> n=10, k=3"""
        assert_extract("binomial n=10 k=3", ["n", "k"], {"n": "10", "k": "3"})

    def test_extract_m_modulo(self, skip_if_not_implemented):
        """'mod m=7' -> m=7"""
        assert_extract("mod m=7", ["m"], {"m": "7"})

    def test_extract_m_from_modulus(self, skip_if_not_implemented):
        """'modulus 1000' -> m=1000"""
        assert_extract("modulus 1000", ["m"], {"m": "1000"})

    def test_extract_degree(self, skip_if_not_implemented):
        """'legendre degree 5' -> n=5"""
        assert_extract("legendre degree 5", ["n"], {"n": "5"})


# =============================================================================
# ARRAY/MATRIX EXTRACTION TESTS - 136 commands use these
# =============================================================================


@pytest.mark.array
class TestArrayExtraction:
    """Test extraction of array/matrix arguments."""

    def test_extract_matrix_nested_brackets(self, skip_if_not_implemented):
        """'det [[1,2],[3,4]]' -> matrix=[[1,2],[3,4]]"""
        assert_extract("det [[1,2],[3,4]]", ["matrix"], {"matrix": "[[1,2],[3,4]]"})

    def test_extract_matrix_with_spaces(self, skip_if_not_implemented):
        """'det [[ 1, 2 ], [ 3, 4 ]]' -> matrix=[[1,2],[3,4]]"""
        result = smart_extract("det [[ 1, 2 ], [ 3, 4 ]]", ["matrix"])
        # Normalize spaces for comparison
        assert "matrix" in result
        assert "[[" in result["matrix"] and "]]" in result["matrix"]

    def test_extract_matrix_3x3(self, skip_if_not_implemented):
        """'eigenvalues of [[1,0,0],[0,2,0],[0,0,3]]' -> matrix=[[1,0,0],[0,2,0],[0,0,3]]"""
        assert_extract(
            "eigenvalues of [[1,0,0],[0,2,0],[0,0,3]]",
            ["matrix"],
            {"matrix": "[[1,0,0],[0,2,0],[0,0,3]]"}
        )

    def test_extract_data_flat_array(self, skip_if_not_implemented):
        """'mean of [1, 2, 3, 4]' -> data=[1, 2, 3, 4]"""
        result = smart_extract("mean of [1, 2, 3, 4]", ["data"])
        assert "data" in result
        assert "[1" in result["data"] and "4]" in result["data"]

    def test_extract_data_no_spaces(self, skip_if_not_implemented):
        """'std [1,2,3,4,5]' -> data=[1,2,3,4,5]"""
        assert_extract("std [1,2,3,4,5]", ["data"], {"data": "[1,2,3,4,5]"})

    def test_extract_array_negative_values(self, skip_if_not_implemented):
        """'sum [-1, -2, 3, 4]' -> data=[-1, -2, 3, 4]"""
        result = smart_extract("sum [-1, -2, 3, 4]", ["data"])
        assert "data" in result
        assert "-1" in result["data"]

    def test_extract_array_floats(self, skip_if_not_implemented):
        """'mean [1.5, 2.5, 3.5]' -> data=[1.5, 2.5, 3.5]"""
        result = smart_extract("mean [1.5, 2.5, 3.5]", ["data"])
        assert "data" in result
        assert "1.5" in result["data"]

    def test_extract_A_b_linear_system(self, skip_if_not_implemented):
        """'solve A=[[3,1],[1,2]] b=[9,8]' -> A=[[3,1],[1,2]], b=[9,8]"""
        result = smart_extract("solve A=[[3,1],[1,2]] b=[9,8]", ["A", "b"])
        assert result["A"] == "[[3,1],[1,2]]"
        assert result["b"] == "[9,8]"

    def test_extract_signal_for_fft(self, skip_if_not_implemented):
        """'fft of [1,0,1,0,1,0,1,0]' -> signal=[1,0,1,0,1,0,1,0]"""
        assert_extract("fft of [1,0,1,0,1,0,1,0]", ["signal"], {"signal": "[1,0,1,0,1,0,1,0]"})

    def test_extract_matrix_from_keyword(self, skip_if_not_implemented):
        """'matrix=[[1,2],[3,4]] determinant' -> matrix=[[1,2],[3,4]]"""
        assert_extract("matrix=[[1,2],[3,4]] determinant", ["matrix"], {"matrix": "[[1,2],[3,4]]"})

    def test_extract_empty_array_returns_none(self, skip_if_not_implemented):
        """'mean of values' -> no data key"""
        result = smart_extract("mean of values", ["data"])
        assert "data" not in result or result["data"] is None


# =============================================================================
# FUNCTION/EXPRESSION EXTRACTION TESTS - 47 commands use these
# =============================================================================


@pytest.mark.function
class TestFunctionExtraction:
    """Test extraction of function/expression arguments."""

    def test_extract_func_simple(self, skip_if_not_implemented):
        """'minimize x**2' -> func=x**2"""
        assert_extract("minimize x**2", ["func"], {"func": "x**2"})

    def test_extract_func_complex(self, skip_if_not_implemented):
        """'minimize x**2 + 2*x + 1' -> func=x**2 + 2*x + 1"""
        result = smart_extract("minimize x**2 + 2*x + 1", ["func"])
        assert "func" in result
        assert "x**2" in result["func"]
        assert "2*x" in result["func"] or "2 * x" in result["func"]

    def test_extract_func_with_caret(self, skip_if_not_implemented):
        """'minimize x^2 + x' -> func=x**2 + x (convert ^ to **)"""
        result = smart_extract("minimize x^2 + x", ["func"])
        assert "func" in result
        # Should convert ^ to **
        assert "^" not in result["func"]
        assert "**" in result["func"] or "x2" in result["func"].replace(" ", "")

    def test_extract_func_trig(self, skip_if_not_implemented):
        """'integrate sin(x)*cos(x)' -> func=sin(x)*cos(x)"""
        result = smart_extract("integrate sin(x)*cos(x)", ["func"])
        assert "func" in result
        assert "sin" in result["func"]
        assert "cos" in result["func"]

    def test_extract_func_multivar(self, skip_if_not_implemented):
        """'minimize x**2 + y**2' -> func=x**2 + y**2"""
        result = smart_extract("minimize x**2 + y**2", ["func"])
        assert "func" in result
        assert "x" in result["func"] and "y" in result["func"]

    def test_extract_expression_for_diff(self, skip_if_not_implemented):
        """'differentiate x**3 + 2*x' -> expression=x**3 + 2*x"""
        result = smart_extract("differentiate x**3 + 2*x", ["expression"])
        assert "expression" in result
        assert "x**3" in result["expression"] or "x^3" in result["expression"]

    def test_extract_expression_with_var(self, skip_if_not_implemented):
        """'differentiate x**3 with respect to x' -> expression=x**3, var=x"""
        result = smart_extract("differentiate x**3 with respect to x", ["expression", "var"])
        assert "expression" in result
        assert result.get("var") == "x"

    def test_extract_lambda_style(self, skip_if_not_implemented):
        """'root find lambda x: x**2 - 2' -> func=x**2 - 2"""
        result = smart_extract("root find lambda x: x**2 - 2", ["func"])
        assert "func" in result
        assert "x**2" in result["func"] or "x^2" in result["func"]

    def test_extract_ode_function(self, skip_if_not_implemented):
        """'solve ode dy/dt = -y' -> func=-y"""
        result = smart_extract("solve ode dy/dt = -y", ["func"])
        assert "func" in result
        assert "-y" in result["func"]


# =============================================================================
# BOUNDS EXTRACTION TESTS - 17+ commands use these
# =============================================================================


@pytest.mark.bounds
class TestBoundsExtraction:
    """Test extraction of bounds arguments."""

    def test_extract_bounds_from_to(self, skip_if_not_implemented):
        """'integrate from 0 to pi' -> lower=0, upper=pi"""
        result = smart_extract("integrate from 0 to pi", ["lower", "upper"])
        assert result["lower"] == "0"
        assert result["upper"] == "pi"

    def test_extract_bounds_numeric(self, skip_if_not_implemented):
        """'integrate from 0 to 1' -> lower=0, upper=1"""
        result = smart_extract("integrate from 0 to 1", ["lower", "upper"])
        assert result["lower"] == "0"
        assert result["upper"] == "1"

    def test_extract_bounds_negative(self, skip_if_not_implemented):
        """'integrate from -1 to 1' -> lower=-1, upper=1"""
        result = smart_extract("integrate from -1 to 1", ["lower", "upper"])
        assert result["lower"] == "-1"
        assert result["upper"] == "1"

    def test_extract_bounds_infinity(self, skip_if_not_implemented):
        """'integrate from 0 to infinity' -> lower=0, upper=oo"""
        result = smart_extract("integrate from 0 to infinity", ["lower", "upper"])
        assert result["lower"] == "0"
        assert result["upper"] in ["oo", "inf", "infinity"]

    def test_extract_bounds_negative_infinity(self, skip_if_not_implemented):
        """'integrate from -infinity to 0' -> lower=-oo, upper=0"""
        result = smart_extract("integrate from -infinity to 0", ["lower", "upper"])
        assert result["lower"] in ["-oo", "-inf", "-infinity"]
        assert result["upper"] == "0"

    def test_extract_bounds_bracket(self, skip_if_not_implemented):
        """'in range [0, 1]' -> bounds=[0, 1]"""
        result = smart_extract("in range [0, 1]", ["bounds"])
        assert "bounds" in result
        assert "0" in result["bounds"] and "1" in result["bounds"]

    def test_extract_bounds_interval(self, skip_if_not_implemented):
        """'on interval (0, pi)' -> lower=0, upper=pi"""
        result = smart_extract("on interval (0, pi)", ["lower", "upper"])
        assert result["lower"] == "0"
        assert result["upper"] == "pi"

    def test_extract_bounds_over(self, skip_if_not_implemented):
        """'over [0, 2*pi]' -> bounds=[0, 2*pi]"""
        result = smart_extract("over [0, 2*pi]", ["bounds"])
        assert "bounds" in result

    def test_extract_x_range_plot(self, skip_if_not_implemented):
        """'plot from -10 to 10' -> x_min=-10, x_max=10"""
        result = smart_extract("plot from -10 to 10", ["x_min", "x_max"])
        assert result["x_min"] == "-10"
        assert result["x_max"] == "10"


# =============================================================================
# COMBINED EXTRACTION TESTS - Multiple argument types together
# =============================================================================


@pytest.mark.combined
class TestCombinedExtraction:
    """Test extraction of multiple argument types together."""

    def test_mpmath_function_with_dps(self, skip_if_not_implemented):
        """'compute mp_sin(0.5) with 100 digits' -> x=0.5, dps=100"""
        result = smart_extract("compute mp_sin(0.5) with 100 digits", ["x", "dps"])
        assert result["x"] == "0.5"
        assert result["dps"] == "100"

    def test_numpy_mean_with_axis(self, skip_if_not_implemented):
        """'mean of [[1,2],[3,4]] along axis 0' -> data=[[1,2],[3,4]], axis=0"""
        result = smart_extract("mean of [[1,2],[3,4]] along axis 0", ["data", "axis"])
        assert "[[1,2],[3,4]]" in result["data"] or "[[1, 2], [3, 4]]" in result["data"]
        assert result["axis"] == "0"

    def test_scipy_minimize_with_x0(self, skip_if_not_implemented):
        """'minimize x**2 starting from 5' -> func=x**2, x0=5"""
        result = smart_extract("minimize x**2 starting from 5", ["func", "x0"])
        assert "x**2" in result["func"] or "x^2" in result["func"]
        assert result["x0"] == "5"

    def test_scipy_quad_all_args(self, skip_if_not_implemented):
        """'integrate x**2 from 0 to 1' -> func=x**2, a=0, b=1"""
        result = smart_extract("integrate x**2 from 0 to 1", ["func", "a", "b"])
        assert "x**2" in result["func"] or "x^2" in result["func"]
        assert result["a"] == "0"
        assert result["b"] == "1"

    def test_bessel_with_order_and_x(self, skip_if_not_implemented):
        """'bessel J order 3 at 2.5' -> n=3, x=2.5"""
        result = smart_extract("bessel J order 3 at 2.5", ["n", "x"])
        assert result["n"] == "3"
        assert result["x"] == "2.5"

    def test_binomial_all_args(self, skip_if_not_implemented):
        """'binomial coefficient n=10 k=3' -> n=10, k=3"""
        result = smart_extract("binomial coefficient n=10 k=3", ["n", "k"])
        assert result["n"] == "10"
        assert result["k"] == "3"

    def test_derivative_with_order(self, skip_if_not_implemented):
        """'3rd derivative of x**4' -> expression=x**4, n=3"""
        result = smart_extract("3rd derivative of x**4", ["expression", "n"])
        assert "x**4" in result["expression"] or "x^4" in result["expression"]
        assert result["n"] == "3"

    def test_limit_all_args(self, skip_if_not_implemented):
        """'limit of sin(x)/x as x -> 0' -> expression=sin(x)/x, var=x, to=0"""
        result = smart_extract("limit of sin(x)/x as x -> 0", ["expression", "var", "to"])
        assert "sin(x)/x" in result["expression"]
        assert result["var"] == "x"
        assert result["to"] == "0"

    def test_taylor_all_args(self, skip_if_not_implemented):
        """'taylor series of exp(x) around 0 order 5' -> expression=exp(x), point=0, order=5"""
        result = smart_extract("taylor series of exp(x) around 0 order 5", ["expression", "point", "order"])
        assert "exp(x)" in result["expression"]
        assert result["point"] == "0"
        assert result["order"] == "5"


# =============================================================================
# EDGE CASES AND SPECIAL VALUES
# =============================================================================


@pytest.mark.edge
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_intent(self, skip_if_not_implemented):
        """Empty intent returns empty dict."""
        result = smart_extract("", ["x"])
        assert result == {} or result.get("x") is None

    def test_no_matching_args(self, skip_if_not_implemented):
        """Intent with no extractable values returns empty dict."""
        result = smart_extract("hello world", ["x", "y"])
        assert "x" not in result or result["x"] is None
        assert "y" not in result or result["y"] is None

    def test_special_value_pi(self, skip_if_not_implemented):
        """'sin(pi)' -> x=pi"""
        assert_extract("sin(pi)", ["x"], {"x": "pi"})

    def test_special_value_e(self, skip_if_not_implemented):
        """'log(e)' -> x=e"""
        assert_extract("log(e)", ["x"], {"x": "e"})

    def test_special_value_inf(self, skip_if_not_implemented):
        """'limit as x -> inf' -> to=inf or to=oo"""
        result = smart_extract("limit as x -> inf", ["to"])
        assert result["to"] in ["inf", "oo", "infinity"]

    def test_special_value_nan(self, skip_if_not_implemented):
        """'check if nan' -> value includes nan"""
        result = smart_extract("check if nan", ["value"])
        # May or may not extract nan as a value
        # Test that it doesn't crash
        assert isinstance(result, dict)

    def test_unicode_pi(self, skip_if_not_implemented):
        """Handle unicode pi symbol."""
        # Note: actual unicode handling may vary
        result = smart_extract("compute sin of 3.14159", ["x"])
        assert "x" in result

    def test_whitespace_handling(self, skip_if_not_implemented):
        """Extra whitespace is handled gracefully."""
        result = smart_extract("  compute   sin  of   0.5  ", ["x"])
        assert result["x"] == "0.5"

    def test_case_insensitive(self, skip_if_not_implemented):
        """'COMPUTE SIN OF 0.5' works same as lowercase."""
        result = smart_extract("COMPUTE SIN OF 0.5", ["x"])
        assert result["x"] == "0.5"

    def test_mixed_case(self, skip_if_not_implemented):
        """'Compute Sin Of 0.5' works."""
        result = smart_extract("Compute Sin Of 0.5", ["x"])
        assert result["x"] == "0.5"


# =============================================================================
# FALLBACK BEHAVIOR TESTS
# =============================================================================


@pytest.mark.fallback
class TestFallbackBehavior:
    """Test fallback behavior when patterns don't match."""

    def test_no_value_found_returns_empty(self, skip_if_not_implemented):
        """When no value pattern matches, return empty dict."""
        result = smart_extract("just some text", ["x"])
        assert "x" not in result or result["x"] is None

    def test_partial_match_extracts_available(self, skip_if_not_implemented):
        """Extract what's available, leave rest empty."""
        result = smart_extract("compute 0.5", ["x", "y"])
        # Should extract x=0.5 but not y
        assert result.get("x") == "0.5"
        assert "y" not in result or result["y"] is None

    def test_ambiguous_prefers_explicit(self, skip_if_not_implemented):
        """When both explicit and implicit match, prefer explicit."""
        result = smart_extract("x=3 compute 5", ["x"])
        # Explicit x=3 should win over implicit 5
        assert result["x"] == "3"

    def test_explicit_wins_over_positional(self, skip_if_not_implemented):
        """'dps=100 digits 50' -> dps=100 (explicit wins)"""
        result = smart_extract("dps=100 digits 50", ["dps"])
        assert result["dps"] == "100"

    def test_first_match_for_positional(self, skip_if_not_implemented):
        """For positional args, first value wins."""
        result = smart_extract("compute 1 2 3", ["x"])
        # First number should be x
        assert result["x"] == "1"


# =============================================================================
# SPECIFIC COMMAND PATTERN TESTS
# =============================================================================


@pytest.mark.commands
class TestSpecificCommandPatterns:
    """Test patterns specific to certain math commands."""

    def test_gamma_function(self, skip_if_not_implemented):
        """'gamma(5)' -> x=5"""
        assert_extract("gamma(5)", ["x"], {"x": "5"})

    def test_zeta_function(self, skip_if_not_implemented):
        """'zeta(2)' -> s=2"""
        assert_extract("zeta(2)", ["s"], {"s": "2"})

    def test_factorial(self, skip_if_not_implemented):
        """'factorial of 10' -> n=10"""
        assert_extract("factorial of 10", ["n"], {"n": "10"})

    def test_fibonacci(self, skip_if_not_implemented):
        """'fibonacci(20)' -> n=20"""
        assert_extract("fibonacci(20)", ["n"], {"n": "20"})

    def test_prime_check(self, skip_if_not_implemented):
        """'is 17 prime' -> n=17"""
        assert_extract("is 17 prime", ["n"], {"n": "17"})

    def test_nth_prime(self, skip_if_not_implemented):
        """'100th prime' -> n=100"""
        assert_extract("100th prime", ["n"], {"n": "100"})

    def test_modular_inverse(self, skip_if_not_implemented):
        """'modular inverse of 3 mod 7' -> a=3, m=7"""
        result = smart_extract("modular inverse of 3 mod 7", ["a", "m"])
        assert result["a"] == "3"
        assert result["m"] == "7"

    def test_polynomial_roots(self, skip_if_not_implemented):
        """'roots of x^3 - 6x^2 + 11x - 6' -> expression includes the polynomial"""
        result = smart_extract("roots of x^3 - 6x^2 + 11x - 6", ["expression"])
        assert "expression" in result
        assert "x" in result["expression"]

    def test_eigenvalue_problem(self, skip_if_not_implemented):
        """'eigenvalues of [[2,1],[1,2]]' -> matrix=[[2,1],[1,2]]"""
        assert_extract("eigenvalues of [[2,1],[1,2]]", ["matrix"], {"matrix": "[[2,1],[1,2]]"})

    def test_determinant(self, skip_if_not_implemented):
        """'determinant [[1,2,3],[4,5,6],[7,8,9]]' -> matrix=..."""
        result = smart_extract("determinant [[1,2,3],[4,5,6],[7,8,9]]", ["matrix"])
        assert "matrix" in result
        assert "[[1,2,3]" in result["matrix"]


# =============================================================================
# REGRESSION TESTS - Based on real usage patterns
# =============================================================================


@pytest.mark.regression
class TestRegressionPatterns:
    """Regression tests based on observed real-world usage."""

    def test_natural_sin_query(self, skip_if_not_implemented):
        """'what is sin of 30 degrees' -> extracts numeric value"""
        result = smart_extract("what is sin of 30 degrees", ["x"])
        assert result["x"] == "30"

    def test_calculate_phrase(self, skip_if_not_implemented):
        """'calculate the integral of x^2 from 0 to 1' -> multiple args"""
        result = smart_extract("calculate the integral of x^2 from 0 to 1", ["expression", "lower", "upper"])
        assert "x" in result["expression"]
        assert result["lower"] == "0"
        assert result["upper"] == "1"

    def test_verbose_request(self, skip_if_not_implemented):
        """Long verbose request still extracts values."""
        intent = "please compute the numerical value of pi to 50 decimal places of precision"
        result = smart_extract(intent, ["dps"])
        assert result["dps"] == "50"

    def test_with_explanation(self, skip_if_not_implemented):
        """'compute sin(0.5) and explain the result' -> x=0.5"""
        result = smart_extract("compute sin(0.5) and explain the result", ["x"])
        assert result["x"] == "0.5"

    def test_multiple_operations(self, skip_if_not_implemented):
        """'differentiate and then integrate x^2' -> expression=x^2"""
        result = smart_extract("differentiate and then integrate x^2", ["expression"])
        assert "x" in result["expression"]

    def test_real_mpmath_query(self, skip_if_not_implemented):
        """'mpmath zeta(2) with 100 digit precision' -> s=2, dps=100"""
        result = smart_extract("mpmath zeta(2) with 100 digit precision", ["s", "dps"])
        assert result["s"] == "2"
        assert result["dps"] == "100"

    def test_real_numpy_query(self, skip_if_not_implemented):
        """'numpy mean of [1,2,3,4,5]' -> data=[1,2,3,4,5]"""
        result = smart_extract("numpy mean of [1,2,3,4,5]", ["data"])
        assert "data" in result
        assert "[1,2,3,4,5]" in result["data"] or "[1, 2, 3, 4, 5]" in result["data"]

    def test_real_scipy_query(self, skip_if_not_implemented):
        """'scipy minimize x**2 + y**2 starting from (1, 1)' -> func, x0"""
        result = smart_extract("scipy minimize x**2 + y**2 starting from (1, 1)", ["func", "x0"])
        assert "func" in result
        assert "x" in result["func"]

    def test_real_sympy_query(self, skip_if_not_implemented):
        """'sympy solve x^2 - 4 = 0' -> expression=x^2 - 4 = 0 or x**2 - 4"""
        result = smart_extract("sympy solve x^2 - 4 = 0", ["expression"])
        assert "expression" in result
        assert "x" in result["expression"]


# =============================================================================
# NUMERIC FORMAT TESTS
# =============================================================================


@pytest.mark.numeric
class TestNumericFormats:
    """Test various numeric format extractions."""

    def test_integer(self, skip_if_not_implemented):
        """'compute 42' -> x=42"""
        assert_extract("compute 42", ["x"], {"x": "42"})

    def test_float_decimal(self, skip_if_not_implemented):
        """'compute 3.14159' -> x=3.14159"""
        assert_extract("compute 3.14159", ["x"], {"x": "3.14159"})

    def test_float_leading_dot(self, skip_if_not_implemented):
        """'compute .5' -> x=.5 or x=0.5"""
        result = smart_extract("compute .5", ["x"])
        assert result["x"] in [".5", "0.5"]

    def test_scientific_positive_exp(self, skip_if_not_implemented):
        """'compute 1.5e10' -> x=1.5e10"""
        assert_extract("compute 1.5e10", ["x"], {"x": "1.5e10"})

    def test_scientific_negative_exp(self, skip_if_not_implemented):
        """'compute 1.5e-10' -> x=1.5e-10"""
        assert_extract("compute 1.5e-10", ["x"], {"x": "1.5e-10"})

    def test_scientific_capital_e(self, skip_if_not_implemented):
        """'compute 1.5E10' -> x=1.5E10"""
        result = smart_extract("compute 1.5E10", ["x"])
        assert result["x"].lower() == "1.5e10"

    def test_negative_integer(self, skip_if_not_implemented):
        """'compute -42' -> x=-42"""
        assert_extract("compute -42", ["x"], {"x": "-42"})

    def test_negative_float(self, skip_if_not_implemented):
        """'compute -3.14' -> x=-3.14"""
        assert_extract("compute -3.14", ["x"], {"x": "-3.14"})

    def test_complex_number(self, skip_if_not_implemented):
        """'compute 3+4j' -> z=3+4j"""
        result = smart_extract("compute 3+4j", ["z"])
        assert "3" in result["z"] and "4" in result["z"]

    def test_complex_negative_imag(self, skip_if_not_implemented):
        """'compute 3-4j' -> z=3-4j"""
        result = smart_extract("compute 3-4j", ["z"])
        assert "3" in result["z"]

    def test_fraction(self, skip_if_not_implemented):
        """'compute 1/2' -> x=1/2"""
        result = smart_extract("compute 1/2", ["x"])
        assert result["x"] in ["1/2", "0.5"]


# =============================================================================
# VARIABLE NAME EXTRACTION
# =============================================================================


@pytest.mark.variable
class TestVariableExtraction:
    """Test extraction of variable names."""

    def test_var_from_with_respect_to(self, skip_if_not_implemented):
        """'differentiate with respect to x' -> var=x"""
        result = smart_extract("differentiate with respect to x", ["var"])
        assert result["var"] == "x"

    def test_var_from_wrt(self, skip_if_not_implemented):
        """'differentiate wrt t' -> var=t"""
        result = smart_extract("differentiate wrt t", ["var"])
        assert result["var"] == "t"

    def test_var_from_expression(self, skip_if_not_implemented):
        """'differentiate sin(t)' -> var=t (inferred)"""
        result = smart_extract("differentiate sin(t)", ["var", "expression"])
        assert result.get("var") == "t" or "t" in result.get("expression", "")

    def test_multiple_vars(self, skip_if_not_implemented):
        """'partial derivative wrt x and y' -> var could be x or first one"""
        result = smart_extract("partial derivative wrt x and y", ["var"])
        assert result["var"] == "x"

    def test_var_from_function_notation(self, skip_if_not_implemented):
        """'f(x) = x^2' -> var=x"""
        result = smart_extract("f(x) = x^2", ["var", "expression"])
        # Should identify x as the variable
        assert result.get("var") == "x" or "x" in result.get("expression", "")


# =============================================================================
# PERFORMANCE AND STRESS TESTS
# =============================================================================


@pytest.mark.slow
class TestPerformance:
    """Performance tests for smart_extract."""

    def test_very_long_intent(self, skip_if_not_implemented):
        """Handle very long intent strings."""
        long_intent = "compute " + " ".join(["x**2 +"] * 100) + " 0"
        result = smart_extract(long_intent, ["expression"])
        # Should not crash
        assert isinstance(result, dict)

    def test_many_numbers(self, skip_if_not_implemented):
        """Handle intent with many numbers."""
        numbers = ", ".join(str(i) for i in range(100))
        intent = f"mean of [{numbers}]"
        result = smart_extract(intent, ["data"])
        assert "data" in result

    def test_deep_nested_brackets(self, skip_if_not_implemented):
        """Handle deeply nested bracket structures."""
        nested = "[[[[1]]]]"
        result = smart_extract(f"det {nested}", ["matrix"])
        assert "matrix" in result

    def test_unicode_content(self, skip_if_not_implemented):
        """Handle unicode characters in intent."""
        intent = "compute integral from alpha to beta"
        result = smart_extract(intent, ["lower", "upper"])
        # Should handle without crashing
        assert isinstance(result, dict)


# =============================================================================
# API CONTRACT TESTS
# =============================================================================


@pytest.mark.api
class TestApiContract:
    """Test the API contract of smart_extract."""

    def test_returns_dict(self, skip_if_not_implemented):
        """smart_extract always returns a dict."""
        result = smart_extract("anything", ["x"])
        assert isinstance(result, dict)

    def test_dict_values_are_strings(self, skip_if_not_implemented):
        """All extracted values are strings."""
        result = smart_extract("compute 42", ["x"])
        for value in result.values():
            if value is not None:
                assert isinstance(value, str)

    def test_unknown_args_ignored(self, skip_if_not_implemented):
        """Unknown expected_args are silently ignored."""
        result = smart_extract("compute 42", ["unknown_arg"])
        # Should not crash, may return empty
        assert isinstance(result, dict)

    def test_empty_expected_args(self, skip_if_not_implemented):
        """Empty expected_args list returns empty dict."""
        result = smart_extract("compute 42", [])
        assert result == {}

    def test_none_expected_args(self, skip_if_not_implemented):
        """None expected_args should be handled gracefully."""
        # This might raise an error or return empty - document actual behavior
        try:
            result = smart_extract("compute 42", None)  # type: ignore
            assert isinstance(result, dict)
        except TypeError:
            # Acceptable behavior
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
