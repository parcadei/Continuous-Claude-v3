---
name: multi-tool-pipeline
description: Template for chaining multiple MCP tools in a single script
allowed-tools: [Bash, Read]
---

# Multi-Tool Pipeline Template

Reference implementation showing how to chain multiple MCP tools in a script.

## When to Use

- As a **template** when creating new MCP pipeline scripts
- To understand the pattern for tool chaining
- When skill-developer needs to create a new pipeline

## The Pattern

```python
async def main():
    from runtime.mcp_client import call_mcp_tool

    # Step 1: First tool
    result1 = await call_mcp_tool("server1__tool1", {"param": "value"})

    # Step 2: Use result in next tool
    result2 = await call_mcp_tool("server2__tool2", {"input": result1})

    # Step 3: Combine/process
    return {"combined": result1, "processed": result2}
```

## Example Implementation

See the reference script:

```bash
cat $CLAUDE_PROJECT_DIR/scripts/multi_tool_pipeline.py
```

Run it:

```bash
uv run python -m runtime.harness scripts/multi_tool_pipeline.py \
    --repo-path "." \
    --max-commits 5
```

## Key Elements

1. **CLI Arguments** - Use argparse for parameters
2. **Sequential Calls** - await each tool before the next
3. **Error Handling** - try/except around the pipeline
4. **Progress Output** - print status for visibility
5. **Structured Return** - return combined results

## Creating Your Own Pipeline

1. Copy `scripts/multi_tool_pipeline.py` as a starting point
2. Replace the tool calls with your MCP servers/tools
3. Adjust CLI arguments for your use case
4. Use `/skill-developer` to wrap it in a skill

## MCP Tool Naming

Tools are named `serverName__toolName` (double underscore):

```python
await call_mcp_tool("git__git_status", {...})
await call_mcp_tool("firecrawl__firecrawl_scrape", {...})
await call_mcp_tool("perplexity__perplexity_ask", {...})
```
