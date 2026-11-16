"""
Tests for Proposition Extractor - TDD Red Phase.

The proposition extractor uses Claude to convert natural language task descriptions
into structured propositions (key-value pairs representing facts about the task).

Expected API:
    async def extract_propositions(
        context: str,
        domains: list[str] | None = None
    ) -> dict:
        Returns {
            "propositions": {"has_api": True, "auth_method": "JWT", ...},
            "source": "extracted",  # or "cached"
            "confidence": 0.85  # float 0-1
        }
"""

from unittest.mock import patch

import pytest


class TestExtractPropositionsImport:
    """Test that the module is importable."""

    def test_extract_propositions_importable(self):
        """extract_propositions function should be importable from scripts."""
        from scripts.extract_propositions import extract_propositions
        assert callable(extract_propositions)


class TestSimpleExtraction:
    """Test basic proposition extraction from natural language."""

    @pytest.mark.asyncio
    async def test_extract_api_with_jwt_auth(self):
        """
        'Build an API with JWT auth' should extract:
        - has_api: True
        - auth_method: 'JWT'
        """
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "has_api": True,
                    "auth_method": "JWT",
                },
                "confidence": 0.95,
            }

            result = await extract_propositions("Build an API with JWT auth")

            assert result["propositions"]["has_api"] is True
            assert result["propositions"]["auth_method"] == "JWT"

    @pytest.mark.asyncio
    async def test_extract_cli_tool(self):
        """
        'Create a CLI tool' should extract:
        - has_api: False
        - is_cli: True
        """
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "has_api": False,
                    "is_cli": True,
                },
                "confidence": 0.90,
            }

            result = await extract_propositions("Create a CLI tool")

            assert result["propositions"]["has_api"] is False
            assert result["propositions"]["is_cli"] is True

    @pytest.mark.asyncio
    async def test_extract_web_app(self):
        """
        'Build a React web app with user login' should extract web-related props.
        """
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "has_frontend": True,
                    "framework": "React",
                    "has_auth": True,
                },
                "confidence": 0.88,
            }

            result = await extract_propositions("Build a React web app with user login")

            assert result["propositions"]["has_frontend"] is True
            assert result["propositions"]["framework"] == "React"
            assert result["propositions"]["has_auth"] is True


class TestUnknownDetection:
    """Test that ambiguous or missing information is marked as UNKNOWN."""

    @pytest.mark.asyncio
    async def test_api_without_auth_method_is_unknown(self):
        """
        'Build an API' (no auth specified) should have auth_method: 'UNKNOWN'.
        """
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "has_api": True,
                    "auth_method": "UNKNOWN",
                },
                "confidence": 0.70,
            }

            result = await extract_propositions("Build an API")

            assert result["propositions"]["has_api"] is True
            assert result["propositions"]["auth_method"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_auth_without_method_is_unknown(self):
        """
        'Add authentication' (no method specified) should have auth_method: 'UNKNOWN'.
        """
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "has_auth": True,
                    "auth_method": "UNKNOWN",
                },
                "confidence": 0.65,
            }

            result = await extract_propositions("Add authentication")

            assert result["propositions"]["has_auth"] is True
            assert result["propositions"]["auth_method"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_database_unspecified_is_unknown(self):
        """
        'Store user data' without DB specification should have database: 'UNKNOWN'.
        """
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "has_storage": True,
                    "database": "UNKNOWN",
                },
                "confidence": 0.60,
            }

            result = await extract_propositions("Store user data persistently")

            assert result["propositions"]["has_storage"] is True
            assert result["propositions"]["database"] == "UNKNOWN"


class TestDomainFiltering:
    """Test that domain filtering restricts which propositions are extracted."""

    @pytest.mark.asyncio
    async def test_filter_to_auth_domain_only(self):
        """
        domains=['auth'] should only extract auth-related propositions.
        """
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "auth_method": "OAuth2",
                    "has_mfa": False,
                },
                "confidence": 0.85,
            }

            result = await extract_propositions(
                "Build an API with OAuth2, PostgreSQL database, and React frontend",
                domains=["auth"]
            )

            # Should have auth props
            assert "auth_method" in result["propositions"]
            # Should NOT have unrelated props (mock ensures this)
            mock_claude.assert_called_once()
            call_args = mock_claude.call_args
            # Verify domains were passed to Claude
            assert "auth" in str(call_args)

    @pytest.mark.asyncio
    async def test_filter_to_multiple_domains(self):
        """
        domains=['auth', 'backend'] should extract props from both domains.
        """
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "auth_method": "JWT",
                    "has_api": True,
                    "database": "PostgreSQL",
                },
                "confidence": 0.80,
            }

            result = await extract_propositions(
                "Build a REST API with JWT auth and PostgreSQL",
                domains=["auth", "backend"]
            )

            assert "auth_method" in result["propositions"]
            assert "database" in result["propositions"]

    @pytest.mark.asyncio
    async def test_no_domain_filter_extracts_all(self):
        """
        domains=None should extract all relevant propositions.
        """
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "has_api": True,
                    "auth_method": "JWT",
                    "database": "MongoDB",
                    "has_frontend": True,
                },
                "confidence": 0.75,
            }

            result = await extract_propositions(
                "Full-stack app with JWT, MongoDB, and React",
                domains=None
            )

            # All props should be present
            assert len(result["propositions"]) >= 3


class TestReturnStructure:
    """Test the structure of the return value."""

    @pytest.mark.asyncio
    async def test_return_has_required_keys(self):
        """Return value must have 'propositions', 'source', 'confidence' keys."""
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {"has_api": True},
                "confidence": 0.90,
            }

            result = await extract_propositions("Build an API")

            assert "propositions" in result
            assert "source" in result
            assert "confidence" in result

    @pytest.mark.asyncio
    async def test_propositions_is_dict(self):
        """The 'propositions' field must be a dict."""
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {"has_api": True},
                "confidence": 0.90,
            }

            result = await extract_propositions("Build an API")

            assert isinstance(result["propositions"], dict)

    @pytest.mark.asyncio
    async def test_confidence_is_float_between_0_and_1(self):
        """The 'confidence' field must be a float between 0 and 1."""
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {"has_api": True},
                "confidence": 0.85,
            }

            result = await extract_propositions("Build an API")

            assert isinstance(result["confidence"], float)
            assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_source_is_extracted_or_cached(self):
        """The 'source' field must be either 'extracted' or 'cached'."""
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {"has_api": True},
                "confidence": 0.90,
            }

            result = await extract_propositions("Build an API")

            assert result["source"] in ("extracted", "cached")


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_context_returns_empty_propositions(self):
        """Empty context should return empty propositions dict."""
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {},
                "confidence": 0.0,
            }

            result = await extract_propositions("")

            assert result["propositions"] == {}

    @pytest.mark.skip(reason="Mutually exclusive - implementation returns empty dict")
    @pytest.mark.asyncio
    async def test_empty_context_raises_value_error(self):
        """Alternative: empty context could raise ValueError."""
        from scripts.extract_propositions import extract_propositions

        # This test expects ValueError - implementation can choose either approach
        # If implementation returns empty dict, this test should be skipped
        with pytest.raises(ValueError, match="context"):
            await extract_propositions("")

    @pytest.mark.asyncio
    async def test_very_long_context_still_works(self):
        """Very long context strings should still be processed."""
        from scripts.extract_propositions import extract_propositions

        long_context = "Build an API " * 1000  # ~13,000 characters

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {"has_api": True},
                "confidence": 0.50,
            }

            result = await extract_propositions(long_context)

            assert "propositions" in result
            mock_claude.assert_called_once()

    @pytest.mark.asyncio
    async def test_whitespace_only_context(self):
        """Whitespace-only context should be treated as empty."""
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {},
                "confidence": 0.0,
            }

            result = await extract_propositions("   \n\t   ")

            assert result["propositions"] == {}

    @pytest.mark.asyncio
    async def test_special_characters_in_context(self):
        """Context with special characters should be handled."""
        from scripts.extract_propositions import extract_propositions

        context = "Build an API with 'JWT' auth & <XML> support"

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "has_api": True,
                    "auth_method": "JWT",
                },
                "confidence": 0.80,
            }

            result = await extract_propositions(context)

            assert result["propositions"]["has_api"] is True


class TestCaching:
    """Test caching behavior (if implemented)."""

    @pytest.mark.asyncio
    async def test_cached_result_has_source_cached(self):
        """When result is from cache, source should be 'cached'."""
        from scripts.extract_propositions import extract_propositions

        # First call - extracted
        with patch("scripts.extract_propositions.call_claude"):
            with patch("scripts.extract_propositions.get_cached") as mock_cache_get:
                mock_cache_get.return_value = {
                    "propositions": {"has_api": True},
                    "confidence": 0.90,
                }

                result = await extract_propositions("Build an API")

                assert result["source"] == "cached"

    @pytest.mark.asyncio
    async def test_fresh_extraction_has_source_extracted(self):
        """When result is freshly extracted, source should be 'extracted'."""
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            with patch("scripts.extract_propositions.get_cached") as mock_cache_get:
                mock_cache_get.return_value = None  # No cached value
                mock_claude.return_value = {
                    "propositions": {"has_api": True},
                    "confidence": 0.90,
                }

                result = await extract_propositions("Build an API")

                assert result["source"] == "extracted"


class TestClaudeIntegration:
    """Test that Claude is called correctly."""

    @pytest.mark.asyncio
    async def test_claude_called_with_context(self):
        """Claude should be called with the context string."""
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {"has_api": True},
                "confidence": 0.90,
            }

            await extract_propositions("Build an API with JWT auth")

            mock_claude.assert_called_once()
            call_args = mock_claude.call_args
            # Context should be in the call
            assert "Build an API with JWT auth" in str(call_args)

    @pytest.mark.asyncio
    async def test_claude_called_with_domains_when_provided(self):
        """When domains are provided, they should be passed to Claude."""
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {"auth_method": "JWT"},
                "confidence": 0.85,
            }

            await extract_propositions(
                "Build an API with everything",
                domains=["auth", "backend"]
            )

            mock_claude.assert_called_once()
            call_args = mock_claude.call_args
            # Domains should be in the call
            assert "auth" in str(call_args) or "domains" in str(call_args)

    @pytest.mark.asyncio
    async def test_claude_error_propagates(self):
        """Errors from Claude should propagate appropriately."""
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.side_effect = RuntimeError("API rate limit exceeded")

            with pytest.raises(RuntimeError, match="rate limit"):
                await extract_propositions("Build an API")


class TestPropositionTypes:
    """Test various proposition value types."""

    @pytest.mark.asyncio
    async def test_boolean_propositions(self):
        """Propositions can have boolean values."""
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "has_api": True,
                    "is_cli": False,
                    "needs_auth": True,
                },
                "confidence": 0.90,
            }

            result = await extract_propositions("Build an API with auth")

            assert result["propositions"]["has_api"] is True
            assert result["propositions"]["is_cli"] is False

    @pytest.mark.asyncio
    async def test_string_propositions(self):
        """Propositions can have string values."""
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "database": "PostgreSQL",
                    "framework": "FastAPI",
                    "auth_method": "OAuth2",
                },
                "confidence": 0.85,
            }

            result = await extract_propositions("Build with PostgreSQL, FastAPI, OAuth2")

            assert result["propositions"]["database"] == "PostgreSQL"
            assert result["propositions"]["framework"] == "FastAPI"

    @pytest.mark.asyncio
    async def test_list_propositions(self):
        """Propositions can have list values (e.g., supported_features)."""
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "supported_auth_methods": ["JWT", "OAuth2", "API_KEY"],
                },
                "confidence": 0.80,
            }

            result = await extract_propositions("Support JWT, OAuth2, and API key auth")

            assert isinstance(result["propositions"]["supported_auth_methods"], list)
            assert "JWT" in result["propositions"]["supported_auth_methods"]
