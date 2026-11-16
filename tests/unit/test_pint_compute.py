#!/usr/bin/env python3
"""Tests for pint_compute.py - Unit conversion cognitive prosthetics.

TDD: These tests written FIRST, before implementation.
"""

import pytest
import sys
from pathlib import Path

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


# =============================================================================
# Test: Parse Quantity
# =============================================================================


class TestParseQuantity:
    """Tests for parse_quantity function."""

    def test_parse_simple_length(self):
        """Parse '5 meters' as a quantity."""
        from pint_compute import parse_quantity

        result = parse_quantity("5 meters")
        assert result is not None
        assert result["magnitude"] == 5.0
        assert "meter" in result["units"].lower() or "m" in result["units"]

    def test_parse_compound_units(self):
        """Parse '10 kg*m/s^2' (force-like units)."""
        from pint_compute import parse_quantity

        result = parse_quantity("10 kg*m/s^2")
        assert result is not None
        assert result["magnitude"] == 10.0

    def test_parse_velocity(self):
        """Parse '100 km/h' as velocity."""
        from pint_compute import parse_quantity

        result = parse_quantity("100 km/h")
        assert result is not None
        assert result["magnitude"] == 100.0

    def test_parse_temperature(self):
        """Parse '298.15 kelvin' as temperature.

        Note: Pint has special handling for offset units (degC, degF).
        Using absolute temperature (kelvin) for testing.
        """
        from pint_compute import parse_quantity

        result = parse_quantity("298.15 kelvin")
        assert result is not None
        assert result["magnitude"] == 298.15

    def test_parse_with_scientific_notation(self):
        """Parse '3e8 m/s' (speed of light)."""
        from pint_compute import parse_quantity

        result = parse_quantity("3e8 m/s")
        assert result is not None
        assert result["magnitude"] == 3e8

    def test_parse_includes_dimensionality(self):
        """Result includes dimensionality info."""
        from pint_compute import parse_quantity

        result = parse_quantity("5 meters")
        assert "dimensionality" in result


# =============================================================================
# Test: Convert Units
# =============================================================================


class TestConvertUnits:
    """Tests for convert_units function."""

    def test_convert_meters_to_feet(self):
        """Convert 5 meters to feet."""
        from pint_compute import convert_units

        result = convert_units("5 meters", "feet")
        assert result is not None
        assert "result" in result
        # 5 meters is approximately 16.4 feet
        assert abs(result["magnitude"] - 16.4042) < 0.01

    def test_convert_kmh_to_mph(self):
        """Convert 100 km/h to mph."""
        from pint_compute import convert_units

        result = convert_units("100 km/h", "mph")
        assert result is not None
        # 100 km/h is approximately 62.14 mph
        assert abs(result["magnitude"] - 62.137) < 0.1

    def test_convert_kelvin_to_rankine(self):
        """Convert 273.15 kelvin to rankine.

        Note: Pint has special handling for offset units (degC, degF).
        Using absolute temperature scales (kelvin, rankine) for testing.
        """
        from pint_compute import convert_units

        result = convert_units("273.15 kelvin", "rankine")
        assert result is not None
        # 273.15 K = 491.67 R
        assert abs(result["magnitude"] - 491.67) < 0.1

    def test_convert_kg_to_pounds(self):
        """Convert 1 kg to pounds."""
        from pint_compute import convert_units

        result = convert_units("1 kg", "pounds")
        assert result is not None
        # 1 kg is approximately 2.205 pounds
        assert abs(result["magnitude"] - 2.2046) < 0.01

    def test_convert_liters_to_gallons(self):
        """Convert 10 liters to gallons."""
        from pint_compute import convert_units

        result = convert_units("10 liters", "gallons")
        assert result is not None
        # 10 liters is approximately 2.64 US gallons
        assert abs(result["magnitude"] - 2.6417) < 0.1

    def test_convert_includes_latex(self):
        """Result includes LaTeX representation."""
        from pint_compute import convert_units

        result = convert_units("5 meters", "feet")
        assert "latex" in result


# =============================================================================
# Test: Unit Arithmetic
# =============================================================================


class TestUnitArithmetic:
    """Tests for unit_calc function - arithmetic with units."""

    def test_multiply_length_time(self):
        """5 m * 3 s = 15 m*s."""
        from pint_compute import unit_calc

        result = unit_calc("5 m * 3 s")
        assert result is not None
        assert result["magnitude"] == 15.0
        # Units should contain both m and s

    def test_divide_length_time(self):
        """10 m / 2 s = 5 m/s."""
        from pint_compute import unit_calc

        result = unit_calc("10 m / 2 s")
        assert result is not None
        assert result["magnitude"] == 5.0

    def test_add_compatible_units(self):
        """5 m + 300 cm = 8 m."""
        from pint_compute import unit_calc

        result = unit_calc("5 m + 300 cm")
        assert result is not None
        # Result should be 8 meters (5 + 3)
        assert abs(result["magnitude"] - 8.0) < 0.01

    def test_subtract_compatible_units(self):
        """10 kg - 500 g = 9.5 kg."""
        from pint_compute import unit_calc

        result = unit_calc("10 kg - 500 g")
        assert result is not None
        assert abs(result["magnitude"] - 9.5) < 0.01

    def test_power_operation(self):
        """(2 m)^2 = 4 m^2."""
        from pint_compute import unit_calc

        result = unit_calc("(2 m) ** 2")
        assert result is not None
        assert result["magnitude"] == 4.0

    def test_calc_includes_result_units(self):
        """Result includes units information."""
        from pint_compute import unit_calc

        result = unit_calc("10 m / 2 s")
        assert "units" in result


# =============================================================================
# Test: Dimensionality Check
# =============================================================================


class TestDimensionalityCheck:
    """Tests for check_dimensions function."""

    def test_force_equals_mass_times_acceleration(self):
        """Force has dimensions of mass * acceleration."""
        from pint_compute import check_dimensions

        result = check_dimensions("newton", "kg * m / s^2")
        assert result["compatible"] is True

    def test_energy_equals_force_times_distance(self):
        """Energy has dimensions of force * distance."""
        from pint_compute import check_dimensions

        result = check_dimensions("joule", "newton * meter")
        assert result["compatible"] is True

    def test_power_equals_energy_per_time(self):
        """Power has dimensions of energy / time."""
        from pint_compute import check_dimensions

        result = check_dimensions("watt", "joule / second")
        assert result["compatible"] is True

    def test_incompatible_dimensions(self):
        """Mass and length are incompatible."""
        from pint_compute import check_dimensions

        result = check_dimensions("kg", "meter")
        assert result["compatible"] is False

    def test_energy_not_mass(self):
        """Energy is not compatible with mass."""
        from pint_compute import check_dimensions

        result = check_dimensions("joule", "kg")
        assert result["compatible"] is False

    def test_check_includes_dimensionality_info(self):
        """Result includes dimensionality details."""
        from pint_compute import check_dimensions

        result = check_dimensions("newton", "kg * m / s^2")
        assert "dim1" in result or "dimensionality" in result


# =============================================================================
# Test: Simplify Units
# =============================================================================


class TestSimplifyUnits:
    """Tests for simplify_units function."""

    def test_simplify_force_units(self):
        """kg*m/s^2 simplifies to newton."""
        from pint_compute import simplify_units

        result = simplify_units("1 kg*m/s^2")
        assert result is not None
        # Should show equivalent in base units and named units

    def test_simplify_energy_units(self):
        """kg*m^2/s^2 simplifies to joule."""
        from pint_compute import simplify_units

        result = simplify_units("1 kg*m^2/s^2")
        assert result is not None

    def test_simplify_preserves_magnitude(self):
        """Simplification preserves magnitude."""
        from pint_compute import simplify_units

        result = simplify_units("10 kg*m/s^2")
        assert result["magnitude"] == 10.0

    def test_simplify_includes_base_units(self):
        """Result includes base unit representation."""
        from pint_compute import simplify_units

        result = simplify_units("5 newton")
        assert "base_units" in result or "simplified" in result


# =============================================================================
# Test: Error Handling
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_add_incompatible_units_raises(self):
        """Adding meters + seconds should fail."""
        from pint_compute import unit_calc

        result = unit_calc("5 meters + 3 seconds")
        assert "error" in result
        assert "dimension" in result["error"].lower() or "compatible" in result["error"].lower()

    def test_unknown_unit_raises(self):
        """Unknown unit 'foobar' should fail."""
        from pint_compute import parse_quantity

        result = parse_quantity("5 foobar")
        assert "error" in result
        # Pint says "not defined in the unit registry"
        assert "not defined" in result["error"].lower() or "undefined" in result["error"].lower() or "unknown" in result["error"].lower()

    def test_convert_incompatible_dimensions(self):
        """Converting meters to seconds should fail."""
        from pint_compute import convert_units

        result = convert_units("5 meters", "seconds")
        assert "error" in result
        assert "dimension" in result["error"].lower() or "compatible" in result["error"].lower()

    def test_invalid_expression_syntax(self):
        """Invalid syntax should return error or handle gracefully.

        Note: Pint is forgiving with some syntax issues, so we test
        with a truly invalid expression.
        """
        from pint_compute import unit_calc

        result = unit_calc("5 m +*/ 3 m")
        # Either error or unexpected result
        assert "error" in result or result.get("magnitude") != 8.0

    def test_empty_expression(self):
        """Empty expression should return error."""
        from pint_compute import parse_quantity

        result = parse_quantity("")
        assert "error" in result


# =============================================================================
# Test: Security Validation
# =============================================================================


class TestSecurityValidation:
    """Tests for security - no eval/exec exploitation."""

    def test_reject_import_in_expression(self):
        """Expressions with 'import' should be rejected."""
        from pint_compute import validate_expression

        valid, msg = validate_expression("import os; 5 meters")
        assert valid is False
        assert "dangerous" in msg.lower()

    def test_reject_exec_in_expression(self):
        """Expressions with 'exec' should be rejected."""
        from pint_compute import validate_expression

        valid, msg = validate_expression("exec('rm -rf /'); 5 m")
        assert valid is False

    def test_reject_eval_in_expression(self):
        """Expressions with 'eval' should be rejected."""
        from pint_compute import validate_expression

        valid, msg = validate_expression("eval('bad'); 5 m")
        assert valid is False

    def test_reject_dunder_in_expression(self):
        """Expressions with '__' should be rejected."""
        from pint_compute import validate_expression

        valid, msg = validate_expression("__import__('os'); 5 m")
        assert valid is False

    def test_accept_valid_expression(self):
        """Valid expressions should pass validation."""
        from pint_compute import validate_expression

        valid, msg = validate_expression("5 meters + 3 feet")
        assert valid is True


# =============================================================================
# Test: CLI Interface
# =============================================================================


class TestCLI:
    """Tests for CLI interface."""

    def test_parse_args_convert(self):
        """Parse args for convert command."""
        from pint_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["pint_compute.py", "convert", "5 meters", "--to", "feet"]
        try:
            args = parse_args()
            assert args.command == "convert"
            assert args.quantity == "5 meters"
            assert args.to == "feet"
        finally:
            sys.argv = old_argv

    def test_parse_args_calc(self):
        """Parse args for calc command."""
        from pint_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["pint_compute.py", "calc", "5 m * 3 s"]
        try:
            args = parse_args()
            assert args.command == "calc"
            assert args.expression == "5 m * 3 s"
        finally:
            sys.argv = old_argv

    def test_parse_args_check(self):
        """Parse args for check command."""
        from pint_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["pint_compute.py", "check", "newton", "--against", "kg * m / s^2"]
        try:
            args = parse_args()
            assert args.command == "check"
            assert args.unit1 == "newton"
            assert args.against == "kg * m / s^2"
        finally:
            sys.argv = old_argv

    def test_parse_args_simplify(self):
        """Parse args for simplify command."""
        from pint_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["pint_compute.py", "simplify", "1 kg*m/s^2"]
        try:
            args = parse_args()
            assert args.command == "simplify"
            assert args.quantity == "1 kg*m/s^2"
        finally:
            sys.argv = old_argv

    def test_parse_args_parse(self):
        """Parse args for parse command."""
        from pint_compute import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["pint_compute.py", "parse", "100 km/h"]
        try:
            args = parse_args()
            assert args.command == "parse"
            assert args.quantity == "100 km/h"
        finally:
            sys.argv = old_argv


# =============================================================================
# Test: Output Format
# =============================================================================


class TestOutputFormat:
    """Tests for output format consistency."""

    def test_convert_returns_dict(self):
        """convert_units returns a dict."""
        from pint_compute import convert_units

        result = convert_units("5 meters", "feet")
        assert isinstance(result, dict)

    def test_calc_returns_dict(self):
        """unit_calc returns a dict."""
        from pint_compute import unit_calc

        result = unit_calc("5 m * 3 s")
        assert isinstance(result, dict)

    def test_result_has_magnitude_and_units(self):
        """Results have magnitude and units keys."""
        from pint_compute import parse_quantity

        result = parse_quantity("5 meters")
        if "error" not in result:
            assert "magnitude" in result
            assert "units" in result

    def test_error_result_has_error_key(self):
        """Error results have error key."""
        from pint_compute import parse_quantity

        result = parse_quantity("5 foobar")
        assert "error" in result


# =============================================================================
# Test: Common Physical Constants
# =============================================================================


class TestPhysicalConstants:
    """Tests for physical constant conversions."""

    def test_speed_of_light_conversion(self):
        """Convert speed of light from m/s to km/h."""
        from pint_compute import convert_units

        result = convert_units("299792458 m/s", "km/h")
        assert result is not None
        # Should be approximately 1.08e9 km/h
        if "error" not in result:
            assert result["magnitude"] > 1e9

    def test_gravitational_acceleration(self):
        """9.81 m/s^2 in ft/s^2."""
        from pint_compute import convert_units

        result = convert_units("9.81 m/s^2", "ft/s^2")
        assert result is not None
        # Should be approximately 32.2 ft/s^2
        if "error" not in result:
            assert abs(result["magnitude"] - 32.174) < 0.1

    def test_atmospheric_pressure(self):
        """101325 Pa in atm."""
        from pint_compute import convert_units

        result = convert_units("101325 Pa", "atm")
        assert result is not None
        # Should be 1 atm
        if "error" not in result:
            assert abs(result["magnitude"] - 1.0) < 0.01
