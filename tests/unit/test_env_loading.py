"""Tests for .env file loading and variable expansion."""

import json
import os
from pathlib import Path

import pytest


class TestEnvExpansion:
    """Test environment variable expansion in config."""

    def test_expand_env_vars_in_string(self):
        """Should expand ${VAR} syntax in strings."""
        from runtime.env_utils import expand_env_vars

        os.environ["TEST_API_KEY"] = "secret123"
        result = expand_env_vars("Bearer ${TEST_API_KEY}")
        assert result == "Bearer secret123"

    def test_expand_missing_var_returns_empty(self):
        """Should return empty string for missing vars."""
        from runtime.env_utils import expand_env_vars

        # Ensure var doesn't exist
        os.environ.pop("NONEXISTENT_VAR", None)
        result = expand_env_vars("${NONEXISTENT_VAR}")
        assert result == ""

    def test_expand_with_default_value(self):
        """Should support ${VAR:-default} syntax."""
        from runtime.env_utils import expand_env_vars

        os.environ.pop("MISSING_VAR", None)
        result = expand_env_vars("${MISSING_VAR:-fallback}")
        assert result == "fallback"

    def test_expand_in_dict(self):
        """Should recursively expand vars in dicts."""
        from runtime.env_utils import expand_env_vars_in_config

        os.environ["MY_KEY"] = "myvalue"
        config = {
            "headers": {"Authorization": "Bearer ${MY_KEY}"},
            "env": {"API_KEY": "${MY_KEY}"},
        }
        result = expand_env_vars_in_config(config)
        assert result["headers"]["Authorization"] == "Bearer myvalue"
        assert result["env"]["API_KEY"] == "myvalue"

    def test_expand_in_list(self):
        """Should expand vars in list items."""
        from runtime.env_utils import expand_env_vars_in_config

        os.environ["ARG_VAL"] = "expanded"
        config = {"args": ["--key", "${ARG_VAL}"]}
        result = expand_env_vars_in_config(config)
        assert result["args"] == ["--key", "expanded"]

    def test_non_string_values_unchanged(self):
        """Should leave non-string values unchanged."""
        from runtime.env_utils import expand_env_vars_in_config

        config = {"timeout": 30, "enabled": True, "items": None}
        result = expand_env_vars_in_config(config)
        assert result == config


class TestDotenvLoading:
    """Test .env file loading."""

    def test_load_dotenv_from_project_root(self, tmp_path, monkeypatch):
        """Should load .env from project root."""
        from runtime.env_utils import load_project_env

        # Create .env in tmp_path
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_FROM_DOTENV=loaded_value\n")

        # Change to tmp_path
        monkeypatch.chdir(tmp_path)

        # Clear any existing value
        os.environ.pop("TEST_FROM_DOTENV", None)

        # Load
        load_project_env()

        assert os.environ.get("TEST_FROM_DOTENV") == "loaded_value"

    def test_dotenv_does_not_override_existing(self, tmp_path, monkeypatch):
        """Should not override existing env vars."""
        from runtime.env_utils import load_project_env

        # Set existing value
        os.environ["EXISTING_VAR"] = "original"

        # Create .env with different value
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_VAR=from_dotenv\n")

        monkeypatch.chdir(tmp_path)
        load_project_env()

        # Should keep original
        assert os.environ.get("EXISTING_VAR") == "original"

    def test_missing_dotenv_is_ok(self, tmp_path, monkeypatch):
        """Should not error if .env doesn't exist."""
        from runtime.env_utils import load_project_env

        monkeypatch.chdir(tmp_path)
        # Should not raise
        load_project_env()
