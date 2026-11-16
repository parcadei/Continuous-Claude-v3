from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class AstGrepParams(BaseModel):
    """Parameters for ast_grep"""
    pattern: str
    """AST pattern to search for using ast-grep syntax (e.g., 'console.log($MSG)', 'function $NAME($ARGS) { $$$BODY }')"""
    replacement: Optional[str] = None
    """Replacement pattern (optional). If provided, performs replacement instead of search. Uses same variable syntax as pattern."""
    path: Optional[str] = None
    """File or directory to search in. Defaults to current working directory."""
    glob: Optional[str] = None
    """Glob pattern to filter files (e.g. '*.js', '**/*.{ts,tsx}')"""
    language: Optional[Literal["javascript", "typescript", "python", "rust", "go", "java", "c", "cpp", "csharp", "html", "css", "json", "yaml", "bash", "lua", "php", "ruby", "swift", "kotlin", "dart", "scala"]] = None
    """Target language for parsing. Auto-detected if not specified."""
    mode: Optional[Literal["search", "replace", "count"]] = None
    """Operation mode"""
    context: Optional[float] = None
    """Number of lines to show around matches (like grep -C)"""
    dry_run: Optional[bool] = None
    """Preview changes without modifying files (default: true for replace mode)"""
    head_limit: Optional[float] = None
    """Limit output to first N matches"""

async def ast_grep(params: AstGrepParams) -> Dict[str, Any]:
    """
    A powerful AST-based code search and refactoring tool that understands code structure across 20+ programming languages. Performs syntax-aware pattern matching and transformations.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("ast-grep__ast_grep", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "ast-grep")

    return normalized
