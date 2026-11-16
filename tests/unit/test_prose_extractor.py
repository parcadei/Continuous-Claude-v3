"""Tests for prose E(X,Q) extraction.

TDD: Write failing tests first, then implement to pass.

The prose extractor uses LLM analysis to identify implicit parameters
and unknowns from natural language skill definitions.
"""
import pytest
from unittest.mock import AsyncMock, patch

# Import will fail until we create the module - this is expected in TDD
from scripts.skill_prose_extractor import (
    extract_eqx_from_prose,
    ProseExtractionResult,
    _parse_llm_response,
)


class TestProseExtractor:
    """Tests for extract_eqx_from_prose function."""

    @pytest.mark.asyncio
    async def test_extract_returns_correct_structure(self):
        """Extraction result should have parameters, unknowns, z3_checkable."""
        prose = "Use JWT or OAuth for authentication."

        # Mock LLM response
        mock_response = {
            "parameters": {
                "auth_method": {
                    "type": "enum",
                    "values": ["JWT", "OAuth"],
                    "required": True
                }
            },
            "unknowns": {},
            "z3_checkable": ["auth_method"]
        }

        with patch(
            'scripts.skill_prose_extractor._call_extraction_llm',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await extract_eqx_from_prose(prose)

        assert "parameters" in result
        assert "unknowns" in result
        assert "z3_checkable" in result

    @pytest.mark.asyncio
    async def test_extract_enum_from_prose(self):
        """Should identify enum parameters from 'X or Y' patterns."""
        prose = "Use JWT or OAuth for authentication."

        mock_response = {
            "parameters": {
                "auth_method": {
                    "type": "enum",
                    "values": ["JWT", "OAuth"],
                    "required": True
                }
            },
            "unknowns": {},
            "z3_checkable": ["auth_method"]
        }

        with patch(
            'scripts.skill_prose_extractor._call_extraction_llm',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await extract_eqx_from_prose(prose)

        assert "auth_method" in result["parameters"]
        param = result["parameters"]["auth_method"]
        assert param["type"] == "enum"
        assert "JWT" in param["values"]
        assert "OAuth" in param["values"]

    @pytest.mark.asyncio
    async def test_extract_marks_unspecified_as_unknown(self):
        """Parameters without default values should be UNKNOWN."""
        prose = "Configure the database connection."

        mock_response = {
            "parameters": {
                "database_type": {
                    "type": "string",
                    "required": True
                }
            },
            "unknowns": {"database_type": "UNKNOWN"},
            "z3_checkable": []
        }

        with patch(
            'scripts.skill_prose_extractor._call_extraction_llm',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await extract_eqx_from_prose(prose)

        assert result["unknowns"]["database_type"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_extract_identifies_z3_checkable(self):
        """Should mark enum/bool/int params as Z3-checkable."""
        prose = "Enable verbose mode (true/false) with timeout 30-300 seconds."

        mock_response = {
            "parameters": {
                "verbose": {"type": "bool", "default": False},
                "timeout": {"type": "int", "min": 30, "max": 300}
            },
            "unknowns": {},
            "z3_checkable": ["verbose", "timeout"]
        }

        with patch(
            'scripts.skill_prose_extractor._call_extraction_llm',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await extract_eqx_from_prose(prose)

        assert "verbose" in result["z3_checkable"]
        assert "timeout" in result["z3_checkable"]

    @pytest.mark.asyncio
    async def test_extract_from_debug_skill_prose(self):
        """Extract params from realistic debug skill prose."""
        prose = '''
        # Debug
        You are tasked with helping debug issues during manual testing.
        ...investigate logs, database state, and git history...

        ## Process
        1. Check error logs at the configured log location
        2. Query database for relevant state
        3. Review git history for recent changes
        '''

        mock_response = {
            "parameters": {
                "log_location": {"type": "string", "required": True},
                "database_type": {"type": "string", "required": False},
                "log_format": {"type": "enum", "values": ["json", "plain"], "required": False}
            },
            "unknowns": {
                "log_location": "UNKNOWN",
                "log_format": "UNKNOWN"
            },
            "z3_checkable": ["log_format"]
        }

        with patch(
            'scripts.skill_prose_extractor._call_extraction_llm',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await extract_eqx_from_prose(prose)

        # Should identify implicit parameters
        assert "log_location" in result["parameters"]
        assert "log_format" in result["unknowns"]

    @pytest.mark.asyncio
    async def test_empty_prose_returns_empty_result(self):
        """Empty prose should return empty but valid structure."""
        prose = ""

        mock_response = {
            "parameters": {},
            "unknowns": {},
            "z3_checkable": []
        }

        with patch(
            'scripts.skill_prose_extractor._call_extraction_llm',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            result = await extract_eqx_from_prose(prose)

        assert result["parameters"] == {}
        assert result["unknowns"] == {}
        assert result["z3_checkable"] == []


class TestParseLLMResponse:
    """Tests for _parse_llm_response helper."""

    def test_parse_valid_json(self):
        """Should parse valid JSON response."""
        response = '{"parameters": {"x": {}}, "unknowns": {}, "z3_checkable": []}'
        result = _parse_llm_response(response)
        assert result["parameters"] == {"x": {}}

    def test_parse_json_with_markdown(self):
        """Should extract JSON from markdown code blocks."""
        response = '''```json
{"parameters": {"x": {}}, "unknowns": {}, "z3_checkable": []}
```'''
        result = _parse_llm_response(response)
        assert result["parameters"] == {"x": {}}

    def test_parse_handles_missing_fields(self):
        """Should provide defaults for missing fields."""
        response = '{"parameters": {"x": {}}}'
        result = _parse_llm_response(response)
        assert "unknowns" in result
        assert "z3_checkable" in result

    def test_parse_invalid_json_raises(self):
        """Should raise on unparseable response."""
        response = "This is not JSON at all"
        with pytest.raises(ValueError):
            _parse_llm_response(response)


class TestProseExtractionResult:
    """Tests for ProseExtractionResult TypedDict structure."""

    def test_result_has_required_keys(self):
        """Result type should have all required keys."""
        result: ProseExtractionResult = {
            "parameters": {},
            "unknowns": {},
            "z3_checkable": []
        }
        assert "parameters" in result
        assert "unknowns" in result
        assert "z3_checkable" in result

    def test_parameters_nested_structure(self):
        """Parameters should support nested param definitions."""
        result: ProseExtractionResult = {
            "parameters": {
                "auth_method": {
                    "type": "enum",
                    "values": ["JWT", "OAuth"],
                    "required": True,
                    "default": "JWT"
                }
            },
            "unknowns": {},
            "z3_checkable": ["auth_method"]
        }
        assert result["parameters"]["auth_method"]["type"] == "enum"
        assert result["parameters"]["auth_method"]["values"] == ["JWT", "OAuth"]
