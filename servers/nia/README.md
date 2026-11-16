# nia MCP Tools

Auto-generated wrappers for nia MCP server.

## Tools

- `index`: Index repo/docs/paper. Auto-detects type from URL. Use manage_resource(action='status') to monitor.
- `search`: Search repos/docs. Omit sources for universal hybrid search.
- `manage_resource`: Manage indexed resources (list/status/rename/delete).
- `get_github_file_tree`: Get repo file tree from GitHub API (no indexing needed).
- `nia_web_search`: Web search for repos/docs/tech content.
- `nia_deep_research_agent`: AI-powered deep research on any topic.
- `read_source_content`: Read full content of source file/document.
- `doc_tree`: Get docs tree structure.
- `doc_ls`: List docs directory contents.
- `doc_read`: Read docs page by virtual path.
- `doc_grep`: Regex search in docs.
- `code_grep`: Regex search in repo code.
- `nia_package_search_grep`: Regex search in public package source.
- `nia_package_search_hybrid`: Semantic search in package source with optional regex.
- `nia_package_search_read_file`: Read lines from package source file.
- `nia_bug_report`: Submit bug/feature request.
- `context`: Cross-agent context sharing (save/list/retrieve/search/update/delete).

## Usage

```python
from servers.nia import index

# Use the tool
result = await index(params)
```

**Note**: This file is auto-generated. Do not edit manually.
