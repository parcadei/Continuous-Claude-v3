from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class WarpgrepCodebaseSearchParams(BaseModel):
    """Parameters for warpgrep_codebase_search"""
    search_string: str
    """Search problem statement that this subagent is supposed to research for"""
    repo_path: str
    """The absolute path of the folder where the search should be performed. In multi-repo workspaces, you have to specify a subfolder where the search should be performed, to avoid searching across all repos"""

async def warpgrep_codebase_search(params: WarpgrepCodebaseSearchParams) -> Dict[str, Any]:
    """
    A search subagent the user refers to as 'WarpGrep' that is ideal for exploring the codebase based on a request. This tool invokes a subagent that runs parallel grep and readfile calls over multiple turns to locate line ranges and files which might be relevant to the request. The search term should be a targeted natural language query based on what you are trying to accomplish, like 'Find where authentication requests are handled in the Express routes' or 'Modify the agentic rollout to use the new tokenizer and chat template' or 'Fix the bug where the user gets redirected from the /feed page'. Fill out extra details that you as a smart model can infer in the question to aid the subagent in its search. You should ALWAYS use this tool to start your search.Note: The files and line ranges returned by this tool may be some of the ones needed to complete the user's request, but you should be careful in evaluating the relevance of the results, since the subagent might make mistakes. You should consider using classical search tools afterwards to locate the rest, but only if necessary. 

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("morph__warpgrep_codebase_search", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "morph")

    return normalized
