"""Tests for schema E(X,Q) extraction.

TDD: Write failing tests first, then implement to pass.

The schema extractor directly parses typed parameter schemas (no LLM needed).
"""
import pytest

from scripts.skill_schema_extractor import (
    extract_eqx_from_schema,
    SchemaExtractionResult,
)


class TestExtractEqxFromSchema:
    """Tests for extract_eqx_from_schema function."""

    def test_extract_enum_param(self):
        """Enum params should list all values."""
        schema = {
            "parameters": {
                "auth_method": {
                    "type": "enum",
                    "values": ["JWT", "OAuth", "Session"],
                    "required": True
                }
            }
        }
        result = extract_eqx_from_schema(schema)

        assert "auth_method" in result["parameters"]
        assert result["parameters"]["auth_method"]["values"] == ["JWT", "OAuth", "Session"]
        assert "auth_method" in result["z3_checkable"]

    def test_required_without_default_is_unknown(self):
        """Required param without default should be UNKNOWN."""
        schema = {
            "parameters": {
                "api_key": {"type": "string", "required": True}
            }
        }
        result = extract_eqx_from_schema(schema)
        assert result["unknowns"]["api_key"] == "UNKNOWN"

    def test_optional_with_default_is_known(self):
        """Optional param with default is KNOWN (not in unknowns)."""
        schema = {
            "parameters": {
                "timeout": {"type": "int", "default": 30}
            }
        }
        result = extract_eqx_from_schema(schema)
        assert "timeout" not in result["unknowns"]

    def test_required_with_default_is_known(self):
        """Required param with default is KNOWN (not in unknowns)."""
        schema = {
            "parameters": {
                "verbose": {"type": "bool", "required": True, "default": False}
            }
        }
        result = extract_eqx_from_schema(schema)
        assert "verbose" not in result["unknowns"]

    def test_bool_is_z3_checkable(self):
        """Bool params should be Z3-checkable."""
        schema = {
            "parameters": {
                "debug_mode": {"type": "bool", "default": False}
            }
        }
        result = extract_eqx_from_schema(schema)
        assert "debug_mode" in result["z3_checkable"]

    def test_bounded_int_is_z3_checkable(self):
        """Int with min/max should be Z3-checkable."""
        schema = {
            "parameters": {
                "timeout": {"type": "int", "min": 1, "max": 300}
            }
        }
        result = extract_eqx_from_schema(schema)
        assert "timeout" in result["z3_checkable"]

    def test_unbounded_int_not_z3_checkable(self):
        """Int without bounds should NOT be Z3-checkable."""
        schema = {
            "parameters": {
                "count": {"type": "int"}
            }
        }
        result = extract_eqx_from_schema(schema)
        assert "count" not in result["z3_checkable"]

    def test_string_not_z3_checkable(self):
        """String params should NOT be Z3-checkable."""
        schema = {
            "parameters": {
                "name": {"type": "string"}
            }
        }
        result = extract_eqx_from_schema(schema)
        assert "name" not in result["z3_checkable"]

    def test_empty_schema_returns_empty(self):
        """Empty schema should return empty but valid structure."""
        schema = {}
        result = extract_eqx_from_schema(schema)

        assert result["parameters"] == {}
        assert result["unknowns"] == {}
        assert result["z3_checkable"] == []

    def test_schema_with_no_parameters(self):
        """Schema without parameters key should work."""
        schema = {"name": "test-skill"}
        result = extract_eqx_from_schema(schema)

        assert result["parameters"] == {}
        assert result["unknowns"] == {}
        assert result["z3_checkable"] == []

    def test_multiple_params_mixed_types(self):
        """Should handle multiple params of different types."""
        schema = {
            "parameters": {
                "auth_method": {
                    "type": "enum",
                    "values": ["JWT", "OAuth"],
                    "required": True
                },
                "timeout": {"type": "int", "min": 1, "max": 300, "default": 30},
                "verbose": {"type": "bool", "default": False},
                "api_key": {"type": "string", "required": True},
                "output_path": {"type": "string", "default": "/tmp"}
            }
        }
        result = extract_eqx_from_schema(schema)

        # Check parameters captured
        assert len(result["parameters"]) == 5

        # Check unknowns (required without defaults)
        assert "auth_method" in result["unknowns"]
        assert "api_key" in result["unknowns"]
        assert "timeout" not in result["unknowns"]
        assert "verbose" not in result["unknowns"]
        assert "output_path" not in result["unknowns"]

        # Check z3_checkable
        assert "auth_method" in result["z3_checkable"]
        assert "timeout" in result["z3_checkable"]
        assert "verbose" in result["z3_checkable"]
        assert "api_key" not in result["z3_checkable"]
        assert "output_path" not in result["z3_checkable"]


class TestSchemaExtractionResult:
    """Tests for SchemaExtractionResult structure."""

    def test_result_has_required_keys(self):
        """Result should have all required keys."""
        result: SchemaExtractionResult = {
            "parameters": {},
            "unknowns": {},
            "z3_checkable": []
        }
        assert "parameters" in result
        assert "unknowns" in result
        assert "z3_checkable" in result

    def test_result_preserves_param_structure(self):
        """Result should preserve full param spec structure."""
        schema = {
            "parameters": {
                "level": {
                    "type": "enum",
                    "values": ["low", "medium", "high"],
                    "required": True,
                    "default": "medium",
                    "description": "Detail level"
                }
            }
        }
        result = extract_eqx_from_schema(schema)

        param = result["parameters"]["level"]
        assert param["type"] == "enum"
        assert param["values"] == ["low", "medium", "high"]
        assert param["required"] is True
        assert param["default"] == "medium"
        assert param["description"] == "Detail level"
