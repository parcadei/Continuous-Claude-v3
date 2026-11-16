"""Configuration models using Pydantic for MCP Code Execution runtime.

This module defines the configuration structure for MCP servers and provides
validation using Pydantic models.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ServerConfig(BaseModel):
    """Configuration for a single MCP server.

    Supports three transport types:
    - stdio: Process-based (command, args, env)
    - sse: Server-Sent Events (url, headers)
    - http: Streamable HTTP (url, headers)

    Attributes:
        type: Transport type ('stdio', 'sse', or 'http')
        command: The command to execute (stdio only)
        args: List of arguments (stdio only)
        env: Environment variables (stdio only)
        url: Endpoint URL (sse/http only)
        headers: HTTP headers (sse/http only)
        disabled: Whether this server should be skipped
    """

    type: Literal["stdio", "sse", "http"] = Field(
        default="stdio", description="Transport type"
    )

    # stdio fields
    command: str | None = Field(default=None, description="Command to execute (stdio only)")
    args: list[str] = Field(default_factory=list, description="Arguments for command (stdio)")
    env: dict[str, str] | None = Field(
        default=None, description="Environment variables (stdio)"
    )

    # sse/http fields
    url: str | None = Field(default=None, description="Endpoint URL (sse/http only)")
    headers: dict[str, str] | None = Field(
        default=None, description="HTTP headers (sse/http only)"
    )

    # common fields
    disabled: bool = Field(default=False, description="Whether to skip this server")

    @model_validator(mode="after")
    def validate_transport_fields(self) -> "ServerConfig":
        """Validate fields based on transport type."""
        if self.type == "stdio":
            if not self.command:
                raise ValueError("stdio servers require 'command' field")
            if self.command and not self.command.strip():
                raise ValueError("Command cannot be empty")
            # Ensure args is a list
            if self.args is None:
                self.args = []
        elif self.type in ("sse", "http"):
            if not self.url:
                raise ValueError(f"{self.type} servers require 'url' field")
            if self.url and not self.url.strip():
                raise ValueError("URL cannot be empty")
        else:
            raise ValueError(f"Invalid transport type: {self.type}")

        return self


class McpConfig(BaseModel):
    """Root configuration for all MCP servers.

    Attributes:
        mcpServers: Dictionary mapping server names to their configurations
    """

    mcpServers: dict[str, ServerConfig] = Field(
        ..., description="Mapping of server names to configurations"
    )

    @field_validator("mcpServers")
    @classmethod
    def servers_not_empty(cls, v: dict[str, ServerConfig]) -> dict[str, ServerConfig]:
        """Validate that at least one server is configured."""
        if not v:
            raise ValueError("At least one MCP server must be configured")
        return v

    def get_enabled_servers(self) -> dict[str, ServerConfig]:
        """Return only enabled servers.

        Returns:
            Dictionary of server names to configurations for enabled servers only
        """
        return {name: config for name, config in self.mcpServers.items() if not config.disabled}

    def get_server(self, name: str) -> ServerConfig | None:
        """Get configuration for a specific server by name.

        Args:
            name: Server name to look up

        Returns:
            ServerConfig if found, None otherwise
        """
        return self.mcpServers.get(name)

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "McpConfig":
        """Create McpConfig from a dictionary.

        Args:
            config_dict: Dictionary containing configuration data

        Returns:
            Validated McpConfig instance

        Raises:
            ValidationError: If configuration is invalid
        """
        return cls.model_validate(config_dict)

    @classmethod
    def from_json(cls, json_str: str) -> "McpConfig":
        """Create McpConfig from a JSON string.

        Args:
            json_str: JSON string containing configuration

        Returns:
            Validated McpConfig instance

        Raises:
            ValidationError: If configuration is invalid
            JSONDecodeError: If JSON is malformed
        """
        return cls.model_validate_json(json_str)

    def merge(self, other: "McpConfig") -> "McpConfig":
        """Merge another config into this one, with other taking precedence.

        This is used to merge global config with project config, where
        project config overrides global for servers with the same name.

        Args:
            other: Config to merge (takes precedence on conflicts)

        Returns:
            New McpConfig with merged servers
        """
        merged_servers = {**self.mcpServers, **other.mcpServers}
        return McpConfig(mcpServers=merged_servers)
