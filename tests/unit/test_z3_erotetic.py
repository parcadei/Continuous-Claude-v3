"""
Tests for Z3 Erotetic Checker - E(X,Q) Formal Verification via Z3.

TDD Red Phase: These tests define the expected API for check_evocation().
Tests should FAIL initially - the z3_erotetic module does not exist yet.

The Z3-based evocation checker uses constraint solving to determine which
propositions are UNKNOWN (not entailed by the context). This is different
from the LLM-based verifier in scripts/agentica/erotetic_verifier.py.

Expected API:
    from scripts.z3_erotetic import check_evocation

    result = check_evocation({
        "auth_method": True,        # Known true
        "session_duration": False,  # Known false
        "rate_limit": "JWT",        # Known value (string)
        "error_format": "UNKNOWN",  # Unknown - not entailed
        "validation": None,         # Unknown - not entailed (None variant)
    })

    # Result:
    {
        "isEmpty": False,
        "unknowns": ["error_format", "validation"],
        "count": 2
    }

Theory:
    E(X,Q) represents propositions that cannot be entailed (True/False)
    from the context X via question-heuristic Q. When E(X,Q) = {} (empty),
    all propositions are determined and implementation can proceed.
"""

import pytest

# =============================================================================
# Test Module Import
# =============================================================================

class TestZ3EroteticModuleImport:
    """Tests that the z3_erotetic module can be imported."""

    def test_module_importable(self):
        """z3_erotetic module should be importable."""
        # This will fail until the module is created
        from scripts import z3_erotetic
        assert z3_erotetic is not None

    def test_check_evocation_function_exists(self):
        """check_evocation function should be exported."""
        from scripts.z3_erotetic import check_evocation
        assert callable(check_evocation)

    def test_result_type_constants_exported(self):
        """UNKNOWN constant should be exported for convenience."""
        from scripts.z3_erotetic import UNKNOWN
        assert UNKNOWN is not None


# =============================================================================
# Test Return Type Structure
# =============================================================================

class TestReturnStructure:
    """Tests for the structured result returned by check_evocation."""

    def test_returns_dict_with_required_fields(self):
        """check_evocation should return a dict with isEmpty, unknowns, count."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({"prop1": True})

        assert isinstance(result, dict)
        assert "isEmpty" in result
        assert "unknowns" in result
        assert "count" in result

    def test_is_empty_is_boolean(self):
        """isEmpty field should be a boolean."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({"prop1": True})

        assert isinstance(result["isEmpty"], bool)

    def test_unknowns_is_list(self):
        """unknowns field should be a list of strings."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({"prop1": "UNKNOWN"})

        assert isinstance(result["unknowns"], list)
        for item in result["unknowns"]:
            assert isinstance(item, str)

    def test_count_is_int(self):
        """count field should be a non-negative integer."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({"prop1": True})

        assert isinstance(result["count"], int)
        assert result["count"] >= 0


# =============================================================================
# Test Empty Propositions
# =============================================================================

class TestEmptyPropositions:
    """Tests for empty input case."""

    def test_empty_dict_returns_is_empty_true(self):
        """Empty propositions dict should return isEmpty=True."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({})

        assert result["isEmpty"] is True
        assert result["unknowns"] == []
        assert result["count"] == 0

    def test_empty_dict_has_zero_unknowns(self):
        """Empty propositions should have zero unknowns."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({})

        assert len(result["unknowns"]) == 0


# =============================================================================
# Test All Known Values
# =============================================================================

class TestAllKnownValues:
    """Tests for when all propositions have known values."""

    def test_all_true_returns_is_empty_true(self):
        """All True propositions should return isEmpty=True."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "prop1": True,
            "prop2": True,
            "prop3": True,
        })

        assert result["isEmpty"] is True
        assert result["count"] == 0

    def test_all_false_returns_is_empty_true(self):
        """All False propositions should return isEmpty=True."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "prop1": False,
            "prop2": False,
        })

        assert result["isEmpty"] is True
        assert result["count"] == 0

    def test_mixed_true_false_returns_is_empty_true(self):
        """Mix of True and False should return isEmpty=True."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "auth_enabled": True,
            "debug_mode": False,
            "logging": True,
        })

        assert result["isEmpty"] is True
        assert result["unknowns"] == []

    def test_string_values_are_known(self):
        """String values (like 'JWT') should be treated as known."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "auth_method": "JWT",
            "session_format": "cookie",
            "error_style": "JSON",
        })

        assert result["isEmpty"] is True
        assert result["count"] == 0


# =============================================================================
# Test Single Unknown
# =============================================================================

class TestSingleUnknown:
    """Tests for when exactly one proposition is unknown."""

    def test_one_unknown_string_returns_not_empty(self):
        """Single 'UNKNOWN' string should return isEmpty=False."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "prop1": True,
            "prop2": "UNKNOWN",
        })

        assert result["isEmpty"] is False
        assert result["count"] == 1

    def test_one_unknown_in_unknowns_list(self):
        """Single unknown should appear in unknowns list."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "known_prop": True,
            "unknown_prop": "UNKNOWN",
        })

        assert "unknown_prop" in result["unknowns"]
        assert len(result["unknowns"]) == 1

    def test_none_value_is_unknown(self):
        """None value should be treated as unknown."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "known": True,
            "missing": None,
        })

        assert result["isEmpty"] is False
        assert "missing" in result["unknowns"]


# =============================================================================
# Test Multiple Unknowns
# =============================================================================

class TestMultipleUnknowns:
    """Tests for multiple unknown propositions."""

    def test_two_unknowns_correct_count(self):
        """Two unknowns should return count=2."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "prop1": True,
            "prop2": "UNKNOWN",
            "prop3": "UNKNOWN",
        })

        assert result["count"] == 2

    def test_two_unknowns_both_in_list(self):
        """Both unknowns should appear in unknowns list."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "known": False,
            "unknown1": "UNKNOWN",
            "unknown2": None,
        })

        assert "unknown1" in result["unknowns"]
        assert "unknown2" in result["unknowns"]
        assert len(result["unknowns"]) == 2

    def test_many_unknowns(self):
        """Should handle many unknowns correctly."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "auth_method": "UNKNOWN",
            "session_duration": None,
            "error_format": "UNKNOWN",
            "rate_limiting": "UNKNOWN",
            "validation_rules": None,
        })

        assert result["isEmpty"] is False
        assert result["count"] == 5
        assert len(result["unknowns"]) == 5


# =============================================================================
# Test Mixed Known/Unknown
# =============================================================================

class TestMixedKnownUnknown:
    """Tests for realistic mixed propositions."""

    def test_mixed_returns_only_unknowns(self):
        """Should only list unknowns, not known props."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "auth_method": "JWT",           # Known (string)
            "session_duration": True,       # Known (bool)
            "error_format": "UNKNOWN",      # Unknown
            "logging_enabled": False,       # Known (bool)
            "rate_limit": None,             # Unknown
        })

        assert result["isEmpty"] is False
        assert result["count"] == 2
        assert "error_format" in result["unknowns"]
        assert "rate_limit" in result["unknowns"]
        # Known props should NOT be in unknowns
        assert "auth_method" not in result["unknowns"]
        assert "session_duration" not in result["unknowns"]
        assert "logging_enabled" not in result["unknowns"]

    def test_all_known_no_unknowns_in_list(self):
        """When all known, unknowns list should be empty."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "prop1": True,
            "prop2": "value",
            "prop3": False,
            "prop4": 42,
        })

        assert result["unknowns"] == []


# =============================================================================
# Test UNKNOWN String Handling
# =============================================================================

class TestUnknownStringHandling:
    """Tests for different representations of UNKNOWN."""

    def test_uppercase_unknown_string(self):
        """'UNKNOWN' (uppercase) should be treated as unknown."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({"prop": "UNKNOWN"})

        assert result["isEmpty"] is False
        assert "prop" in result["unknowns"]

    def test_lowercase_unknown_string_is_known(self):
        """'unknown' (lowercase) should be treated as known value."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({"prop": "unknown"})

        # Lowercase 'unknown' is just a string value, not the sentinel
        assert result["isEmpty"] is True
        assert result["count"] == 0

    def test_none_is_unknown(self):
        """None should be treated as unknown."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({"prop": None})

        assert result["isEmpty"] is False
        assert "prop" in result["unknowns"]

    def test_empty_string_is_known(self):
        """Empty string '' should be treated as known value."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({"prop": ""})

        assert result["isEmpty"] is True
        assert result["count"] == 0


# =============================================================================
# Test Using Exported UNKNOWN Constant
# =============================================================================

class TestUnknownConstant:
    """Tests using the exported UNKNOWN constant."""

    def test_using_unknown_constant(self):
        """Using UNKNOWN constant should mark as unknown."""
        from scripts.z3_erotetic import UNKNOWN, check_evocation

        result = check_evocation({"prop": UNKNOWN})

        assert result["isEmpty"] is False
        assert "prop" in result["unknowns"]

    def test_constant_equals_string_unknown(self):
        """UNKNOWN constant should equal the string 'UNKNOWN'."""
        from scripts.z3_erotetic import UNKNOWN

        assert UNKNOWN == "UNKNOWN"


# =============================================================================
# Test Consistency Invariants
# =============================================================================

class TestConsistencyInvariants:
    """Tests for logical consistency between fields."""

    def test_count_equals_len_unknowns(self):
        """count should always equal len(unknowns)."""
        from scripts.z3_erotetic import check_evocation

        test_cases = [
            {},
            {"a": True},
            {"a": "UNKNOWN"},
            {"a": True, "b": "UNKNOWN"},
            {"a": "UNKNOWN", "b": None, "c": "UNKNOWN"},
        ]

        for props in test_cases:
            result = check_evocation(props)
            assert result["count"] == len(result["unknowns"]), \
                f"count mismatch for props={props}"

    def test_is_empty_true_implies_count_zero(self):
        """isEmpty=True implies count=0."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({"prop1": True, "prop2": False})

        if result["isEmpty"]:
            assert result["count"] == 0

    def test_count_zero_implies_is_empty_true(self):
        """count=0 implies isEmpty=True."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({"prop": "value"})

        if result["count"] == 0:
            assert result["isEmpty"] is True

    def test_count_nonzero_implies_is_empty_false(self):
        """count > 0 implies isEmpty=False."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({"prop": "UNKNOWN"})

        if result["count"] > 0:
            assert result["isEmpty"] is False


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_numeric_values_are_known(self):
        """Numeric values (int, float) should be known."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "int_prop": 42,
            "float_prop": 3.14,
            "zero": 0,
            "negative": -1,
        })

        assert result["isEmpty"] is True
        assert result["count"] == 0

    def test_boolean_false_is_known_not_unknown(self):
        """False (boolean) should NOT be treated as unknown."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({"prop": False})

        assert result["isEmpty"] is True
        assert result["count"] == 0
        assert "prop" not in result["unknowns"]

    def test_zero_is_known_not_unknown(self):
        """0 (zero) should NOT be treated as unknown (truthy check trap)."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({"prop": 0})

        assert result["isEmpty"] is True
        assert "prop" not in result["unknowns"]

    def test_empty_list_value_is_known(self):
        """Empty list [] should be known (not unknown)."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({"prop": []})

        assert result["isEmpty"] is True

    def test_empty_dict_value_is_known(self):
        """Empty dict {} as value should be known."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({"prop": {}})

        assert result["isEmpty"] is True

    def test_special_prop_names(self):
        """Should handle special property names correctly."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "snake_case": True,
            "camelCase": True,
            "with-dashes": True,
            "with.dots": True,
            "123numeric": "UNKNOWN",
        })

        assert result["count"] == 1
        assert "123numeric" in result["unknowns"]


# =============================================================================
# Test List Values (Nested Propositions)
# =============================================================================

class TestNestedValues:
    """Tests for nested/complex value types."""

    def test_list_of_values_is_known(self):
        """List with values should be treated as known."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "allowed_methods": ["GET", "POST", "PUT"],
        })

        assert result["isEmpty"] is True

    def test_dict_value_is_known(self):
        """Dict as value should be treated as known."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "config": {"key": "value"},
        })

        assert result["isEmpty"] is True


# =============================================================================
# Test Unknowns List Order
# =============================================================================

class TestUnknownsListProperties:
    """Tests for properties of the unknowns list."""

    def test_unknowns_list_has_no_duplicates(self):
        """unknowns list should not have duplicates."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "prop1": "UNKNOWN",
            "prop2": None,
            "prop3": "UNKNOWN",
        })

        assert len(result["unknowns"]) == len(set(result["unknowns"]))

    def test_unknowns_are_strings(self):
        """All items in unknowns should be strings (prop names)."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "a": "UNKNOWN",
            "b": None,
            123: "UNKNOWN",  # Non-string key
        })

        for item in result["unknowns"]:
            assert isinstance(item, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
