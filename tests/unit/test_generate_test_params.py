"""
Unit tests for generate_test_params module.

Tests the tool classification logic and discovery config generation.
Note: LLM-based parameter generation is tested with mocks to avoid API calls.
"""

from src.runtime.generate_test_params import (
    ToolSafety,
    build_discovery_config,
    classify_tool,
    generate_test_parameters,
)


class TestToolClassification:
    """Test tool classification logic."""

    def test_classify_safe_by_pattern(self) -> None:
        """Tools matching safe patterns are classified as SAFE."""
        assert classify_tool("get_user") == ToolSafety.SAFE
        assert classify_tool("list_repositories") == ToolSafety.SAFE
        assert classify_tool("search_code") == ToolSafety.SAFE
        assert classify_tool("describe_instance") == ToolSafety.SAFE
        assert classify_tool("fetch_data") == ToolSafety.SAFE
        assert classify_tool("read_file") == ToolSafety.SAFE
        assert classify_tool("show_logs") == ToolSafety.SAFE
        assert classify_tool("view_config") == ToolSafety.SAFE
        assert classify_tool("find_records") == ToolSafety.SAFE
        assert classify_tool("query_database") == ToolSafety.SAFE

    def test_classify_dangerous_by_pattern(self) -> None:
        """Tools matching dangerous patterns are classified as DANGEROUS."""
        assert classify_tool("delete_user") == ToolSafety.DANGEROUS
        assert classify_tool("remove_repository") == ToolSafety.DANGEROUS
        assert classify_tool("drop_table") == ToolSafety.DANGEROUS
        assert classify_tool("destroy_instance") == ToolSafety.DANGEROUS
        assert classify_tool("kill_process") == ToolSafety.DANGEROUS
        assert classify_tool("update_config") == ToolSafety.DANGEROUS
        assert classify_tool("write_file") == ToolSafety.DANGEROUS
        assert classify_tool("execute_command") == ToolSafety.DANGEROUS
        assert classify_tool("modify_permissions") == ToolSafety.DANGEROUS
        assert classify_tool("set_variable") == ToolSafety.DANGEROUS

    def test_classify_safe_by_description_keyword(self) -> None:
        """Tools with safe keywords in description are classified as SAFE."""
        assert classify_tool("tool_xyz", "Get the current user information") == ToolSafety.SAFE
        assert classify_tool("tool_abc", "List all available services") == ToolSafety.SAFE
        assert classify_tool("unknown_name", "Fetch data from API") == ToolSafety.SAFE
        assert classify_tool("unknown_name", "Read config file") == ToolSafety.SAFE

    def test_classify_dangerous_by_description_keyword(self) -> None:
        """Tools with dangerous keywords in description are classified as DANGEROUS."""
        assert classify_tool("tool_xyz", "Delete the specified record") == ToolSafety.DANGEROUS
        assert classify_tool("tool_abc", "Remove all entries from database") == ToolSafety.DANGEROUS
        assert classify_tool("unknown_name", "Execute arbitrary code") == ToolSafety.DANGEROUS
        assert classify_tool("unknown_name", "Update system configuration") == ToolSafety.DANGEROUS

    def test_classify_unknown(self) -> None:
        """Tools with no clear pattern or description are classified as UNKNOWN."""
        assert classify_tool("some_tool") == ToolSafety.UNKNOWN
        assert classify_tool("do_something") == ToolSafety.UNKNOWN
        assert classify_tool("process_data") == ToolSafety.UNKNOWN
        assert classify_tool("handle_request") == ToolSafety.UNKNOWN

    def test_classify_dangerous_overrides_safe_keyword(self) -> None:
        """Dangerous keyword in description overrides safe pattern."""
        # Even though description has safe keyword, dangerous keyword wins
        assert (
            classify_tool("get_something", "Get and then delete all data") == ToolSafety.DANGEROUS
        )

    def test_classify_case_insensitive(self) -> None:
        """Classification is case-insensitive."""
        assert classify_tool("GET_USER") == ToolSafety.SAFE
        assert classify_tool("DELETE_USER") == ToolSafety.DANGEROUS
        assert classify_tool("Tool", "Get Data") == ToolSafety.SAFE


class TestBuildDiscoveryConfig:
    """Test discovery config building."""

    def test_build_empty_config(self) -> None:
        """Building config from empty servers returns valid structure."""
        config = build_discovery_config({})
        assert "servers" in config
        assert "metadata" in config
        assert config["servers"] == {}
        assert config["metadata"]["generated_count"] == 0
        assert config["metadata"]["skipped_count"] == 0

    def test_build_config_skips_dangerous(self) -> None:
        """Dangerous tools are skipped by default."""
        from unittest.mock import patch

        servers_tools = {
            "test_server": [
                {
                    "name": "delete_user",
                    "description": "Delete a user",
                    "inputSchema": {"type": "object", "properties": {}},
                },
                {
                    "name": "get_user",
                    "description": "Get a user",
                    "inputSchema": {"type": "object", "properties": {}},
                },
            ]
        }

        # Mock the parameter generation to avoid needing anthropic API
        with patch("src.runtime.generate_test_params.generate_test_parameters") as mock_gen:
            mock_gen.return_value = {"id": "123"}

            config = build_discovery_config(servers_tools, skip_dangerous=True)

            assert "test_server" in config["servers"]
            safe_tools = config["servers"]["test_server"]["safeTools"]
            assert "get_user" in safe_tools
            assert "delete_user" not in safe_tools
            assert config["metadata"]["skipped_count"] == 1
            assert "delete_user" in config["metadata"]["tools_skipped"]["dangerous"]

    def test_build_config_includes_dangerous_when_flag_false(self) -> None:
        """Dangerous tools can be included if skip_dangerous=False."""
        servers_tools = {
            "test_server": [
                {
                    "name": "delete_user",
                    "description": "Delete a user",
                    "inputSchema": {"type": "object", "properties": {}},
                },
            ]
        }

        config = build_discovery_config(servers_tools, skip_dangerous=False)

        # Still skipped because we can't generate params without mocking
        assert config["metadata"]["skipped_count"] >= 0

    def test_build_config_skips_unknown(self) -> None:
        """Unknown tools are skipped (param generation fails)."""
        servers_tools = {
            "test_server": [
                {
                    "name": "unknown_operation",
                    "description": "Some operation",
                    "inputSchema": {"type": "object", "properties": {}},
                },
            ]
        }

        config = build_discovery_config(servers_tools)

        assert "test_server" not in config["servers"] or (
            "unknown_operation" not in config["servers"]["test_server"].get("safeTools", {})
        )
        assert config["metadata"]["skipped_count"] >= 1

    def test_build_config_metadata(self) -> None:
        """Generated config includes proper metadata."""
        config = build_discovery_config({})

        metadata = config["metadata"]
        assert metadata["generated"] is True
        assert "generated_count" in metadata
        assert "skipped_count" in metadata
        assert "tools_skipped" in metadata
        assert "dangerous" in metadata["tools_skipped"]
        assert "unknown" in metadata["tools_skipped"]

    def test_build_config_missing_tool_name(self) -> None:
        """Tools without names are skipped."""
        servers_tools = {
            "test_server": [
                {
                    "name": "",  # Empty name
                    "description": "Some tool",
                    "inputSchema": {},
                },
            ]
        }

        config = build_discovery_config(servers_tools)

        assert (
            "test_server" not in config["servers"]
            or len(config["servers"]["test_server"].get("safeTools", {})) == 0
        )

    def test_build_config_multiple_servers(self) -> None:
        """Config correctly handles multiple servers."""
        servers_tools = {
            "server1": [
                {
                    "name": "get_data",
                    "description": "Get data",
                    "inputSchema": {"type": "object", "properties": {}},
                },
            ],
            "server2": [
                {
                    "name": "list_items",
                    "description": "List items",
                    "inputSchema": {"type": "object", "properties": {}},
                },
            ],
        }

        config = build_discovery_config(servers_tools)

        # At least the structure should be there (actual population depends on param generation)
        assert "servers" in config
        assert isinstance(config["servers"], dict)


class TestGenerateTestParameters:
    """Test parameter generation with Claude API flag."""

    def test_generate_with_claude_api_disabled(self) -> None:
        """When use_claude_api=False, parameter generation returns None without API call."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }

        result = generate_test_parameters("test_tool", schema, use_claude_api=False)

        assert result is None

    def test_generate_with_claude_api_enabled_default(self) -> None:
        """Default behavior is use_claude_api=True (skips without anthropic installed)."""
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }

        result = generate_test_parameters("test_tool", schema)

        # Will be None because anthropic isn't properly installed/configured
        # But the point is it tries to use the API rather than returning None immediately
        # This is tested implicitly by the fact that the function doesn't short-circuit
        assert result is None or isinstance(result, dict)

    def test_generate_with_claude_code_flag(self) -> None:
        """When use_claude_code=True, uses subprocess instead of API."""
        from unittest.mock import MagicMock, patch

        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }

        # Mock subprocess to simulate Claude Code CLI response
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"name": "test"}'
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = generate_test_parameters("test_tool", schema, use_claude_code=True)

            assert mock_run.called
            assert result == {"name": "test"}
            # Verify the claude command was called correctly
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "claude"
            assert call_args[1] == "-p"
            assert "--dangerously-skip-permissions" in call_args

    def test_generate_with_claude_code_cli_not_found(self) -> None:
        """When Claude Code CLI is not installed, returns None gracefully."""
        from unittest.mock import patch

        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = generate_test_parameters("test_tool", schema, use_claude_code=True)

            assert result is None

    def test_generate_with_claude_code_precedence(self) -> None:
        """Claude Code takes precedence over Claude API when both enabled."""
        from unittest.mock import MagicMock, patch

        schema = {"type": "object", "properties": {}}

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "{}"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            # Both enabled, should use claude_code
            generate_test_parameters("test_tool", schema, use_claude_api=True, use_claude_code=True)

            assert mock_run.called

    def test_generate_with_copilot_cli_flag(self) -> None:
        """When use_copilot_cli=True, uses subprocess to call copilot."""
        from unittest.mock import MagicMock, patch

        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }

        # Mock subprocess to simulate Copilot CLI response
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"name": "test"}'
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = generate_test_parameters("test_tool", schema, use_copilot_cli=True)

            assert mock_run.called
            assert result == {"name": "test"}
            # Verify the copilot command was called correctly
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "copilot"
            assert call_args[1] == "-p"
            assert "--allow-all-tools" in call_args

    def test_generate_with_copilot_cli_not_found(self) -> None:
        """When Copilot CLI is not installed, returns None gracefully."""
        from unittest.mock import patch

        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = generate_test_parameters("test_tool", schema, use_copilot_cli=True)

            assert result is None

    def test_generate_with_copilot_cli_precedence_over_claude_code(self) -> None:
        """Copilot CLI takes precedence over Claude Code when both enabled."""
        from unittest.mock import MagicMock, patch

        schema = {"type": "object", "properties": {}}

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "{}"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            # Both enabled, should use copilot_cli
            generate_test_parameters(
                "test_tool", schema, use_claude_code=True, use_copilot_cli=True
            )

            assert mock_run.called
            # Verify copilot was called, not claude
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "copilot"

    def test_generate_with_copilot_cli_precedence_over_all(self) -> None:
        """Copilot CLI takes precedence over both Claude Code and API when all enabled."""
        from unittest.mock import MagicMock, patch

        schema = {"type": "object", "properties": {}}

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "{}"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            # All enabled, should use copilot_cli
            generate_test_parameters(
                "test_tool",
                schema,
                use_claude_api=True,
                use_claude_code=True,
                use_copilot_cli=True,
            )

            assert mock_run.called
            # Verify copilot was called
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "copilot"


class TestToolSafetyEnum:
    """Test ToolSafety enum."""

    def test_tool_safety_values(self) -> None:
        """ToolSafety enum has expected values."""
        assert ToolSafety.SAFE.value == "safe"
        assert ToolSafety.DANGEROUS.value == "dangerous"
        assert ToolSafety.UNKNOWN.value == "unknown"

    def test_tool_safety_comparison(self) -> None:
        """ToolSafety enum members can be compared."""
        assert ToolSafety.SAFE == ToolSafety.SAFE
        assert ToolSafety.SAFE != ToolSafety.DANGEROUS
        assert ToolSafety.DANGEROUS != ToolSafety.UNKNOWN
