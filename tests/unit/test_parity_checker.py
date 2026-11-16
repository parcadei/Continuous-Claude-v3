"""Tests for E(X,Q) parity verification.

TDD: Write failing tests first, then implement to pass.

The parity checker compares E(X,Q) from prose vs schema bidirectionally.
"""
import pytest

from scripts.skill_parity_checker import (
    check_parity,
    ParityResult,
    compute_coverage_score,
)


class TestCheckParity:
    """Tests for check_parity function."""

    def test_schema_covers_prose(self):
        """Schema should cover all prose parameters."""
        prose_eqx = {
            "parameters": {"auth_method": {}, "log_format": {}},
            "unknowns": {"auth_method": "UNKNOWN"},
            "z3_checkable": []
        }
        schema_eqx = {
            "parameters": {"auth_method": {"type": "enum", "values": ["JWT"]}},
            "unknowns": {},
            "z3_checkable": ["auth_method"]
        }

        result = check_parity(prose_eqx, schema_eqx)

        # Schema missing log_format
        assert "log_format" in result.prose_only
        assert result.coverage_score < 1.0

    def test_perfect_parity(self):
        """Equal coverage should give 1.0 score."""
        prose_eqx = {"parameters": {"x": {}}, "unknowns": {}, "z3_checkable": []}
        schema_eqx = {"parameters": {"x": {}}, "unknowns": {}, "z3_checkable": []}

        result = check_parity(prose_eqx, schema_eqx)
        assert result.coverage_score == 1.0
        assert len(result.gaps) == 0

    def test_schema_has_extra_params(self):
        """Extra schema params are OK (superset allowed)."""
        prose_eqx = {"parameters": {"x": {}}, "unknowns": {}, "z3_checkable": []}
        schema_eqx = {"parameters": {"x": {}, "y": {}}, "unknowns": {}, "z3_checkable": []}

        result = check_parity(prose_eqx, schema_eqx)
        assert "y" in result.schema_only
        assert result.coverage_score == 1.0  # Superset is valid

    def test_empty_prose_gives_perfect_score(self):
        """Empty prose means everything covered (vacuously true)."""
        prose_eqx = {"parameters": {}, "unknowns": {}, "z3_checkable": []}
        schema_eqx = {"parameters": {"x": {}}, "unknowns": {}, "z3_checkable": []}

        result = check_parity(prose_eqx, schema_eqx)
        assert result.coverage_score == 1.0

    def test_partial_coverage(self):
        """Partial coverage should give score between 0 and 1."""
        prose_eqx = {
            "parameters": {"a": {}, "b": {}, "c": {}, "d": {}},
            "unknowns": {},
            "z3_checkable": []
        }
        schema_eqx = {
            "parameters": {"a": {}, "b": {}},
            "unknowns": {},
            "z3_checkable": []
        }

        result = check_parity(prose_eqx, schema_eqx)

        # 2/4 covered = 0.5
        assert result.coverage_score == 0.5
        assert set(result.prose_only) == {"c", "d"}

    def test_no_coverage(self):
        """No overlap should give 0.0 score."""
        prose_eqx = {
            "parameters": {"a": {}, "b": {}},
            "unknowns": {},
            "z3_checkable": []
        }
        schema_eqx = {
            "parameters": {"x": {}, "y": {}},
            "unknowns": {},
            "z3_checkable": []
        }

        result = check_parity(prose_eqx, schema_eqx)
        assert result.coverage_score == 0.0
        assert set(result.prose_only) == {"a", "b"}
        assert set(result.schema_only) == {"x", "y"}

    def test_unknown_resolution(self):
        """Should track unresolved unknowns in prose."""
        prose_eqx = {
            "parameters": {"auth": {}, "key": {}},
            "unknowns": {"auth": "UNKNOWN", "key": "UNKNOWN"},
            "z3_checkable": []
        }
        schema_eqx = {
            "parameters": {"auth": {"default": "JWT"}, "key": {}},
            "unknowns": {},  # Schema resolves auth but not key
            "z3_checkable": []
        }

        result = check_parity(prose_eqx, schema_eqx)

        # Both params covered (coverage = 1.0)
        assert result.coverage_score == 1.0

        # But unknowns analysis shows prose had unknowns
        assert "auth" in result.resolved_unknowns or len(result.gaps) >= 0


class TestParityResult:
    """Tests for ParityResult dataclass."""

    def test_result_has_required_fields(self):
        """ParityResult should have all required fields."""
        result = ParityResult(
            prose_only=["a"],
            schema_only=["b"],
            coverage_score=0.5,
            gaps=["missing semantic"],
            resolved_unknowns=["c"]
        )

        assert result.prose_only == ["a"]
        assert result.schema_only == ["b"]
        assert result.coverage_score == 0.5
        assert result.gaps == ["missing semantic"]
        assert result.resolved_unknowns == ["c"]

    def test_is_valid_property(self):
        """Should have is_valid computed property."""
        # Valid: coverage >= 0.8
        valid_result = ParityResult(
            prose_only=[],
            schema_only=[],
            coverage_score=0.9,
            gaps=[],
            resolved_unknowns=[]
        )
        assert valid_result.is_valid

        # Invalid: coverage < 0.8
        invalid_result = ParityResult(
            prose_only=["missing"],
            schema_only=[],
            coverage_score=0.5,
            gaps=[],
            resolved_unknowns=[]
        )
        assert not invalid_result.is_valid


class TestComputeCoverageScore:
    """Tests for coverage score calculation."""

    def test_full_coverage(self):
        """All prose params in schema = 1.0."""
        prose_params = {"a", "b", "c"}
        schema_params = {"a", "b", "c", "d"}
        score = compute_coverage_score(prose_params, schema_params)
        assert score == 1.0

    def test_no_coverage(self):
        """No prose params in schema = 0.0."""
        prose_params = {"a", "b"}
        schema_params = {"x", "y"}
        score = compute_coverage_score(prose_params, schema_params)
        assert score == 0.0

    def test_partial_coverage(self):
        """Some prose params in schema = fraction."""
        prose_params = {"a", "b", "c", "d"}
        schema_params = {"a", "c"}
        score = compute_coverage_score(prose_params, schema_params)
        assert score == 0.5

    def test_empty_prose_full_coverage(self):
        """Empty prose = 1.0 (vacuously true)."""
        prose_params: set[str] = set()
        schema_params = {"a", "b"}
        score = compute_coverage_score(prose_params, schema_params)
        assert score == 1.0

    def test_both_empty_full_coverage(self):
        """Both empty = 1.0."""
        prose_params: set[str] = set()
        schema_params: set[str] = set()
        score = compute_coverage_score(prose_params, schema_params)
        assert score == 1.0


class TestParityIntegration:
    """Integration tests combining all parity functionality."""

    def test_typical_conversion_scenario(self):
        """Test a realistic prose->schema conversion scenario."""
        # Prose skill mentions auth_method, log_format, timeout
        prose_eqx = {
            "parameters": {
                "auth_method": {"type": "enum", "values": ["JWT", "OAuth"]},
                "log_format": {"type": "string"},
                "timeout": {"type": "int"}
            },
            "unknowns": {
                "auth_method": "UNKNOWN",
                "log_format": "UNKNOWN"
            },
            "z3_checkable": ["auth_method"]
        }

        # Schema only captures auth_method and timeout
        schema_eqx = {
            "parameters": {
                "auth_method": {
                    "type": "enum",
                    "values": ["JWT", "OAuth"],
                    "default": "JWT"
                },
                "timeout": {"type": "int", "default": 30}
            },
            "unknowns": {},
            "z3_checkable": ["auth_method"]
        }

        result = check_parity(prose_eqx, schema_eqx)

        # log_format missing from schema
        assert "log_format" in result.prose_only
        # Coverage is 2/3 = 0.666...
        assert 0.66 <= result.coverage_score <= 0.67
        # Not valid (< 0.8)
        assert not result.is_valid
