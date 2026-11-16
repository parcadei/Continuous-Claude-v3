"""
Unit tests for OEIS lookup script.
Tests follow TDD - written before implementation.
"""

import pytest
from unittest.mock import patch, Mock
import json

# Sample OEIS API response for Fibonacci sequence search
SAMPLE_OEIS_SEARCH_RESPONSE = {
    "greeting": "Greetings from The On-Line Encyclopedia of Integer Sequences!",
    "query": "1,1,2,3,5,8,13",
    "count": 2,
    "start": 0,
    "results": [
        {
            "number": 45,
            "id": "M0692",
            "name": "Fibonacci numbers: F(n) = F(n-1) + F(n-2) with F(0) = 0 and F(1) = 1.",
            "data": "0,1,1,2,3,5,8,13,21,34,55,89,144,233,377,610,987,1597,2584,4181",
            "keyword": "nonn,core,nice,easy,hear,changed",
            "offset": "0,4",
            "author": "_N. J. A. Sloane_",
            "references": 123,
            "formula": ["F(n) = F(n-1) + F(n-2) for n > 1.", "F(n) = round(phi^n/sqrt(5))"],
            "comment": ["The Fibonacci sequence is ubiquitous in nature."],
        },
        {
            "number": 71,
            "id": "M1082",
            "name": "Lucas numbers: L(n) = L(n-1) + L(n-2) with L(0) = 2 and L(1) = 1.",
            "data": "2,1,3,4,7,11,18,29,47,76,123,199,322,521,843,1364,2207,3571",
            "keyword": "nonn,nice,easy",
            "offset": "0,1",
            "author": "_N. J. A. Sloane_",
            "formula": ["L(n) = F(n-1) + F(n+1)"],
        },
    ],
}

# Sample response for a specific sequence lookup
SAMPLE_FIBONACCI_RESPONSE = {
    "greeting": "Greetings from The On-Line Encyclopedia of Integer Sequences!",
    "query": "A000045",
    "count": 1,
    "start": 0,
    "results": [
        {
            "number": 45,
            "id": "M0692",
            "name": "Fibonacci numbers: F(n) = F(n-1) + F(n-2) with F(0) = 0 and F(1) = 1.",
            "data": "0,1,1,2,3,5,8,13,21,34,55,89,144,233,377,610,987,1597,2584,4181",
            "keyword": "nonn,core,nice,easy,hear,changed",
            "offset": "0,4",
            "author": "_N. J. A. Sloane_",
            "references": 123,
            "formula": ["F(n) = F(n-1) + F(n-2) for n > 1.", "F(n) = round(phi^n/sqrt(5))"],
            "comment": ["The Fibonacci sequence is ubiquitous in nature."],
        }
    ],
}

# Sample response for prime numbers search
SAMPLE_PRIME_RESPONSE = {
    "greeting": "Greetings from OEIS",
    "query": "prime numbers",
    "count": 1,
    "start": 0,
    "results": [
        {
            "number": 40,
            "name": "The prime numbers.",
            "data": "2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61,67,71",
            "keyword": "nonn,core,nice,easy",
            "formula": [],
        }
    ],
}

# Empty response
SAMPLE_EMPTY_RESPONSE = {
    "greeting": "Greetings from OEIS",
    "query": "xyznonexistent999",
    "count": 0,
    "start": 0,
    "results": None,
}


class TestOeisSearch:
    """Tests for OEIS sequence search functionality."""

    @patch("requests.get")
    def test_search_fibonacci_sequence(self, mock_get):
        """Search by sequence terms should find Fibonacci."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_OEIS_SEARCH_RESPONSE
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.oeis_lookup import search_oeis

        result = search_oeis("1,1,2,3,5,8,13")

        assert "results" in result
        assert len(result["results"]) > 0
        assert any("Fibonacci" in r.get("name", "") for r in result["results"])

    @patch("requests.get")
    def test_search_by_keyword(self, mock_get):
        """Search by keyword should return results."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_PRIME_RESPONSE
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.oeis_lookup import search_oeis

        result = search_oeis("prime numbers")

        assert "results" in result
        assert len(result["results"]) > 0
        assert any("prime" in r.get("name", "").lower() for r in result["results"])

    @patch("requests.get")
    def test_search_returns_correct_fields(self, mock_get):
        """Search results should contain expected fields."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_OEIS_SEARCH_RESPONSE
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.oeis_lookup import search_oeis

        result = search_oeis("1,1,2,3,5,8,13")

        assert "results" in result
        first_result = result["results"][0]
        assert "id" in first_result
        assert "name" in first_result
        assert "data" in first_result
        assert first_result["id"].startswith("A")

    @patch("requests.get")
    def test_search_empty_results(self, mock_get):
        """Search with no matches should return empty results."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_EMPTY_RESPONSE
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.oeis_lookup import search_oeis

        result = search_oeis("xyznonexistent999")

        assert "results" in result
        assert len(result["results"]) == 0

    @patch("requests.get")
    def test_search_with_max_results(self, mock_get):
        """Search should respect max_results parameter."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_OEIS_SEARCH_RESPONSE
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.oeis_lookup import search_oeis

        result = search_oeis("1,1,2,3,5,8,13", max_results=1)

        assert "results" in result
        assert len(result["results"]) <= 1

    @patch("requests.get")
    def test_search_api_error(self, mock_get):
        """Search should handle API errors gracefully."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        from scripts.oeis_lookup import search_oeis

        result = search_oeis("1,1,2,3,5,8,13")

        assert "error" in result

    @patch("requests.get")
    def test_search_network_error(self, mock_get):
        """Search should handle network errors gracefully."""
        import requests

        mock_get.side_effect = requests.RequestException("Connection failed")

        from scripts.oeis_lookup import search_oeis

        result = search_oeis("1,1,2,3,5,8,13")

        assert "error" in result


class TestOeisGet:
    """Tests for OEIS sequence retrieval by A-number."""

    @patch("requests.get")
    def test_get_fibonacci(self, mock_get):
        """Get Fibonacci sequence by A-number."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_FIBONACCI_RESPONSE
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.oeis_lookup import get_sequence

        result = get_sequence("A000045")

        assert "name" in result
        assert "Fibonacci" in result["name"]
        assert "data" in result
        assert "id" in result
        assert result["id"] == "A000045"

    @patch("requests.get")
    def test_get_sequence_with_lowercase(self, mock_get):
        """Get sequence should handle lowercase A-number."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_FIBONACCI_RESPONSE
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.oeis_lookup import get_sequence

        result = get_sequence("a000045")

        assert "name" in result
        # Verify the request was made with uppercase
        call_args = mock_get.call_args
        assert "A000045" in call_args[1]["params"]["q"]

    def test_get_invalid_anumber_format(self):
        """Get sequence with invalid A-number should return error."""
        from scripts.oeis_lookup import get_sequence

        result = get_sequence("invalid")

        assert "error" in result

    def test_get_invalid_anumber_no_digits(self):
        """Get sequence with A but no digits should return error."""
        from scripts.oeis_lookup import get_sequence

        result = get_sequence("Axyz")

        assert "error" in result

    @patch("requests.get")
    def test_get_sequence_not_found(self, mock_get):
        """Get sequence that doesn't exist should return error."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_EMPTY_RESPONSE
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.oeis_lookup import get_sequence

        result = get_sequence("A999999")

        assert "error" in result

    @patch("requests.get")
    def test_get_sequence_returns_formulas(self, mock_get):
        """Get sequence should include formulas when available."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_FIBONACCI_RESPONSE
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.oeis_lookup import get_sequence

        result = get_sequence("A000045")

        assert "formulas" in result
        assert len(result["formulas"]) > 0

    @patch("requests.get")
    def test_get_sequence_returns_keywords(self, mock_get):
        """Get sequence should include keywords."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_FIBONACCI_RESPONSE
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        from scripts.oeis_lookup import get_sequence

        result = get_sequence("A000045")

        assert "keywords" in result

    @patch("requests.get")
    def test_get_api_error(self, mock_get):
        """Get should handle API errors gracefully."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        from scripts.oeis_lookup import get_sequence

        result = get_sequence("A000045")

        assert "error" in result


class TestOeisLookupCLI:
    """Tests for command-line interface."""

    @patch("requests.get")
    def test_cli_search_command(self, mock_get):
        """CLI search command should work."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_OEIS_SEARCH_RESPONSE
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "scripts/oeis_lookup.py", "search", "1,1,2,3,5,8,13"],
            capture_output=True,
            text=True,
            cwd="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit",
        )

        # Script should run without error
        assert result.returncode == 0
        # Output should be valid JSON
        output = json.loads(result.stdout)
        assert "results" in output

    @patch("requests.get")
    def test_cli_get_command(self, mock_get):
        """CLI get command should work."""
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_FIBONACCI_RESPONSE
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "scripts/oeis_lookup.py", "get", "A000045"],
            capture_output=True,
            text=True,
            cwd="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit",
        )

        # Script should run without error
        assert result.returncode == 0
        # Output should be valid JSON
        output = json.loads(result.stdout)
        assert "name" in output or "error" in output

    def test_cli_help(self):
        """CLI --help should work."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "scripts/oeis_lookup.py", "--help"],
            capture_output=True,
            text=True,
            cwd="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit",
        )

        assert result.returncode == 0
        assert "search" in result.stdout.lower() or "usage" in result.stdout.lower()

    def test_cli_search_help(self):
        """CLI search --help should work."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "scripts/oeis_lookup.py", "search", "--help"],
            capture_output=True,
            text=True,
            cwd="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit",
        )

        assert result.returncode == 0
