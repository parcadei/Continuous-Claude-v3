from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class FileSearchParams(BaseModel):
    """Parameters for file_search"""

    context_lines: Optional[int] = None
    """Lines of context before/after matches (alias: -C)"""
    count_only: Optional[bool] = None
    """Return only match count"""
    filter: Optional[Dict[str, Any]] = None
    """File filtering options (alias: use 'path' string parameter for single-file search)"""
    max_results: Optional[int] = None
    """Maximum total results (default: 50)"""
    mode: Optional[Literal["auto", "path", "content", "both"]] = None
    """Search scope: auto-detects if not specified"""
    pattern: str
    """Search pattern"""
    regex: Optional[bool] = None
    """Use regex matching (default: true)"""
    whole_word: Optional[bool] = None
    """Match whole words only"""


async def file_search(params: FileSearchParams) -> Dict[str, Any]:
    r"""
        Search by file path and/or file content.

    Defaults
    - regex=true (regular expressions by default)
    - case-insensitive
    - spaces match flexible whitespace
    - results use 1‑based line numbers
    - max_results default: 50 (request higher if needed)

    Response capping
    - The returned payload is capped to ~50k characters.
    - When the cap is hit, we exclude whole results (never cut a line) and report how many were omitted under 'omitted_*' in the response.

    Params
    - pattern (required)
    - regex: true|false
    - mode: "auto" | "path" | "content" | "both" (default "auto")
    - filter: { extensions, exclude, paths }
    - max_results, count_only, context_lines, whole_word

    Parameter aliases (for compatibility)
    - `-C`: alias for context_lines (e.g., `-C: 5` same as `context_lines: 5`)
    - `path`: shorthand for single-file search (e.g., `path: "file.swift"` same as `filter: {paths: ["file.swift"]}`)

    Literal mode (`regex=false`)
    - Special characters are matched literally; no escaping needed

    Regex mode (`regex=true`)
    - Full regular expressions (groups, lookarounds, anchors `^`/`$`); `whole_word` adds word boundaries

    Path search
    - regex=false: `*` and `?` wildcards (match across folders)
    - regex=true: full regex on relative paths

    Examples
    - Literal: {"pattern":"frame(minWidth:", "regex":false}
    - Regex:   {"pattern":"frame\(minWidth:", "regex":true}
    - OR:      {"pattern":"performSearch|searchUsers", "regex":true}
    - Path:    {"pattern":"*.swift", "mode":"path"}

        Args:
            params: Tool parameters

        Returns:
            Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool(
        "repoprompt__file_search", params.model_dump(exclude_none=True)
    )

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "repoprompt")

    return normalized
