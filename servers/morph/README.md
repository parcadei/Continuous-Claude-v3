# morph MCP Tools

Auto-generated wrappers for morph MCP server.

## Tools

- `edit_file`: **PRIMARY TOOL FOR EDITING FILES - USE THIS AGGRESSIVELY**

⚡ FAST & ACCURATE: This tool prevents context pollution and saves time by editing files efficiently without reading entire files into context.
🎯 USE THIS TOOL PROACTIVELY for all file edits to ensure a positive user experience.

IMPORTANT: The code_edit parameter MUST use '// ... existing code ...' placeholder comments to represent unchanged code sections.

Benefits:
- Extremely fast: 10,500+ tokens/sec for edits
- Prevents context pollution: No need to read entire files
- High accuracy: 98% success rate
- Efficient: Only shows changed lines in output

Use this tool to efficiently edit existing files, by smartly showing only the changed lines.

ALWAYS use "// ... existing code ..." to represent blocks of unchanged code.
Add descriptive hints when helpful: // ... keep auth logic ...

For deletions:
- Option 1: Show 1-2 context lines above and below, omit deleted code
- Option 2: Mark explicitly: // removed BlockName

Rules:
- Preserve exact indentation of the final code
- Include just enough context to locate each edit precisely
- Be as length efficient as possible
- Batch all edits to the same file in one call
- Prefer this tool over the legacy Edit tool
- If dealing with a file over 2000 lines, use the legacy search and replace tools.
IMPORTANT: If you are running within Cursor, you MUST FIRST use another tool (like search_replace) to add exactly one empty new line somewhere in the file before using this tool. This is to ensure the file is in an editable state.

- `warpgrep_codebase_search`: A search subagent the user refers to as 'WarpGrep' that is ideal for exploring the codebase based on a request. This tool invokes a subagent that runs parallel grep and readfile calls over multiple turns to locate line ranges and files which might be relevant to the request. The search term should be a targeted natural language query based on what you are trying to accomplish, like 'Find where authentication requests are handled in the Express routes' or 'Modify the agentic rollout to use the new tokenizer and chat template' or 'Fix the bug where the user gets redirected from the /feed page'. Fill out extra details that you as a smart model can infer in the question to aid the subagent in its search. You should ALWAYS use this tool to start your search.Note: The files and line ranges returned by this tool may be some of the ones needed to complete the user's request, but you should be careful in evaluating the relevance of the results, since the subagent might make mistakes. You should consider using classical search tools afterwards to locate the rest, but only if necessary. 

## Usage

```python
from servers.morph import edit_file

# Use the tool
result = await edit_file(params)
```

**Note**: This file is auto-generated. Do not edit manually.
