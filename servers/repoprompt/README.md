# repoprompt MCP Tools

Auto-generated wrappers for repoprompt MCP server.

## Tools

- `manage_workspaces`: Manage workspaces across RepoPrompt windows.

Actions:
• list    – Return all known workspaces (id, name, repoPaths, showing window IDs)
• switch  – Switch a window to a specified workspace
• create  – Create a new workspace (requires user approval)
• delete  – Delete a workspace (requires user approval)
• add_folder – Add a folder to a workspace (requires user approval)
• remove_folder – Remove a folder from a workspace (requires user approval)
• list_tabs  – List compose tabs for the active workspace in a window
• select_tab – Bind this MCP connection to a specific compose tab

Parameters:
- action: "list" | "switch" | "create" | "delete" | "add_folder" | "remove_folder" | "list_tabs" | "select_tab" (required)
- workspace: string                             (required for 'switch', 'delete', 'add_folder', 'remove_folder'; UUID or name)
- name: string                                  (required for 'create'; the new workspace name)
- folder_path: string                           (required for 'add_folder', 'remove_folder'; absolute path)
- tab: string                                   (required for 'select_tab'; UUID or name)
- window_id: integer                            (optional; target window, defaults to selected or only window)
- focus: boolean                                (optional for 'select_tab'; default false)

For 'switch', provide a single 'workspace' value. If it parses as a UUID, that workspace is selected by ID; otherwise it is treated as a name and the first match is used.

After selecting a window (via select_window), use list_tabs and select_tab to pin your connection to a specific compose tab. This ensures your tools operate on consistent context even if the user changes the active tab in the UI.

Tab binding behavior:
• If no tab is bound, tools use the user's currently active tab. This can cause inconsistent results if the user switches tabs during your operations.
• Use select_tab to explicitly bind to a specific tab for predictable, stable context across multiple tool calls.
• Alternatively, pass the hidden '_tabID' parameter with any tool call to bind on-the-fly.

Output flags:
• [active] = The tab currently visible in the UI for that window
• [bound] = The tab this MCP connection is pinned to; your tool calls use this tab even if the user switches the visible tab

IMPORTANT: The 'focus' parameter switches the visible tab in the UI, which can be disruptive to the user's workflow. Only set focus=true when the user explicitly requests to see or switch to a specific tab. For background operations, omit focus or set it to false.
- `manage_selection`: Manage the current selection used by all tools.

Ops: get | add | remove | set | clear | preview | promote | demote
Options:
• view="summary"|"files"|"content" (default "summary")
• path_display="relative"|"full" (default "relative")
• strict=true|false (default false) — if a mutation resolves no paths, return a helpful error; set false for no‑op
• mode="full"|"slices"|"codemap_only" (default "full"):
  - "full": Complete file content
  - "slices": Specific line ranges only
  - "codemap_only": Efficient API structure (function/type signatures) for token savings
  - Files without an available codemap are skipped and reported as "codemap unavailable" when targeting folders or paths in codemap_only mode.

Automatic Codemap Management:
• When selecting files with mode="full" or "slices" (via op=add or op=set), auto-adds codemaps for related/dependency files
• Check complete selection (including auto-codemaps) with op="get" view="files"
• Manual codemap operations (mode="codemap_only", promote, demote) disable auto-management until you clear
• Prefer auto-management; only manually manage when you need precise control

op=set semantics (mode controls behavior):
• mode="full": Clears selection, replaces with provided paths/slices (complete reset)
• mode="slices": File-scoped - adds any paths without clearing, replaces slice definitions only for specified files
• mode="codemap_only": Replaces codemap-only files, disables auto-management

Path Handling:
• Paths can be files or directories (directories are expanded to all files within, recursively)
• Paths can be relative (to workspace root) or absolute
• For single-root workspaces: "src/main.swift" or "Root/src/main.swift" both work
• For multi-root workspaces: prefix with root name (e.g., "ProjectA/src/main.swift")
• Fuzzy matching enabled by default - close matches will be resolved

Guidance:
• Read files with read_file before slicing to identify relevant sections
• Use ranges with descriptions for clarity (aliases: description/desc/label)
• Preview with op="preview" view="files" to see the complete selection (including auto-codemaps) and token counts before committing

Examples:
• Add full file: {"op":"add","paths":["Root/src/main.swift"]}
• Add codemap: {"op":"add","paths":["Root/src/utils/helper.swift"],"mode":"codemap_only"}
• Set slices (file-scoped): {"op":"set","mode":"slices","slices":[{"path":"Root/src/file.swift","ranges":[{"start_line":45,"end_line":120,"description":"UserAuth flow"}]}]}
• Add/merge slices: {"op":"add","slices":[{"path":"Root/src/file.swift","ranges":[{"start_line":200,"end_line":250}]}]}
• Promote codemap→full: {"op":"promote","paths":["Root/src/utils/helper.swift"]}
• Demote full→codemap: {"op":"demote","paths":["Root/src/utils/helper.swift"]}

Related:
• Discover candidates: get_file_tree, file_search
• Preview structure fast: get_code_structure
• Snapshot everything: workspace_context
• Apply changes: apply_edits
• Chat: chat_send (list/log with chats)
- `file_actions`: Create, delete, or move files.

Actions:
- `create`: Create a new file with `content`. Use `if_exists="overwrite"` to replace an existing file. New files are added to the selection.
- `delete`: Delete a file (absolute path required for safety).
- `move`: Move/rename to `new_path` (fails if destination exists).

Paths: Relative or absolute (`delete` requires absolute). When multiple roots are loaded, you must provide an absolute path when creating files; relative paths are rejected to avoid ambiguity.
Options: `if_exists` (create): "error" (default) or "overwrite".

Note: Multi-root file creation is supported. Missing intermediate folders are automatically created.
- `get_code_structure`: Return code structure (codemaps) for files and directories.

Scopes:
- `scope="selected"` — structures for the **current selection** (also lists files without codemaps)
- `scope="paths"` (default) — pass `paths` (files and/or directories; directories are recursive)

Note: Use with `get_file_tree` and `search` to explore before selecting.
- `get_file_tree`: ASCII directory tree of the project.

Types:
- `files` — modes:
	- `auto` (default): tries full tree, then trims depth to fit ~10k tokens
	- `full`: all files/folders (can be very large)
	- `folders`: directories only
	- `selected`: only selected files and their parents
	Optional: `path` to start from a specific folder; `max_depth` to limit (root=0).
- `roots` — list root folders.

Files with a codemap are marked `+` in the standard tree.
- `read_file`: Read file contents, optionally specifying a starting line and number of lines.

Details:
- 1‑based lines; no params → entire file
- `start_line` > 0: start at that line (e.g., 10)
- `start_line` < 0: last N lines (like `tail -n`)
- `limit`: only with positive `start_line` (e.g., start_line=10, limit=20 → lines 10–29)
- `file_search`: Search by file path and/or file content.

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
- `workspace_context`: Snapshot of this window's workspace: prompt, selection, code structure (codemaps). Larger parts are opt-in.
Defaults include: prompt, selection, code, tokens.
include: ["prompt","selection","code","files","tree","tokens"]
path_display: "relative"|"full"

Related: manage_selection (curate selection), prompt (edit instructions), get_file_tree, file_search, get_code_structure, apply_edits, chat_send, chats.
- `prompt`: Get or modify the shared prompt (instructions/notes). Ops: get | set | append | clear

Related: workspace_context (snapshot), manage_selection (files), chat_send (use prompt), apply_edits.
- `apply_edits`: Apply direct file edits (rewrite or search/replace).

Examples:

Single replacement:
`{"path": "file.swift", "search": "oldCode", "replace": "newCode", "all": true}`

Multiple edits:
`{"path": "file.swift", "edits": [{"search": "old1", "replace": "new1"}, {"search": "old2", "replace": "new2"}]}`

Rewrite entire file:
`{"path": "file.swift", "rewrite": "complete file content...", "on_missing": "create"}`

Note: When creating new files (e.g., using `on_missing="create"`), and multiple roots are loaded, you must provide an absolute path within a loaded root; relative paths are rejected to avoid ambiguity. Missing intermediate folders are automatically created.

Options: `verbose` (show diff), `on_missing` (for rewrite: "error" | "create")
- `list_models`: List available model presets (id, name, description, supported modes).
Use before `chat_send` to pick an appropriate preset.
If no presets exist, shows the current chat model. Without `model`, `chat_send` picks the first compatible preset.
- `chat_send`: Start a new chat or continue an existing conversation. Modes: `chat` | `plan` | `edit`.

**Recommended pair‑program loop**
1) **Plan** (`mode="plan"`): ask for architecture/steps or request a review.
2) **Apply**: use `apply_edits` (or `chat_send` with `mode="edit"`) to make the changes.
3) **Review** (`mode="chat"` or `plan`): get a second opinion; refine.
4) **Repeat** in the **same chat**.

**Critical context hygiene**
- Run `manage_selection` op=`get` (view="files") to confirm context and tokens.
- Prefer `set` (or `add`/`remove`) so all **related files** are included.
- For a full snapshot (prompt, selection, code, tokens; optionally file text/tree), call `workspace_context`.
- Bias toward **more context over too little**; avoid selecting only one file that references others.

**Session management**
- `new_chat`: true to start; else continues the most recent (or pass `chat_id`)
- `selected_paths`: replace the selection for this message
- `chat_name`: optional but **highly recommended** — short, descriptive (e.g., "Fix login crash – auth flow")
- `model`: preset id/name; call `list_models` first

**Limitations**
- No commands/tests; only sees **selected files** + conversation history
- For a **snapshot of context** (prompt, selection, codemaps, optional file contents/tree), call `workspace_context`
	(add `"files"` in `include` to embed file text). For targeted slices, use `read_file` or `file_search`.
- The chat does not track diff history; it sees current file state only
- `chats`: List chats or view a chat's history. Actions: list | log

`list`: recent chats (ID, name, selected files, last activity) — use the ID with `chat_send`
`log`: full conversation history (optionally include diffs)

Notes:
- Each chat maintains its own selection and context; continuing restores state
- `chat_send` without `chat_id` resumes the most recent by default
- You can **rename** a session anytime by passing `chat_name` in `chat_send`
Related: chat_send, workspace_context
- `context_builder`: Start a task by intelligently exploring the codebase and building optimal file context.

Ideal as the **first step** for complex tasks: the agent maps out relevant code, selects files
within a token budget, and can generate an implementation plan in one shot. The resulting
chat thread is perfect for follow-up questions, mid-task clarifications, or getting a second
opinion as you work.

**Tips:**
- Use response_type="plan" to get an implementation plan alongside the context, or generate one later via chat_send
- Continue the conversation via chat_send with the returned chat_id
- Add files to the selection with manage_selection as new areas become relevant
- Run context_builder again anytime to explore a different area of the codebase

Parameters:
- instructions: Describe what you want to accomplish
- response_type: "plan" generates an implementation plan; "question" answers about the codebase; omit for context-only

Returns file selection, prompt, and status. With response_type="plan" or "question", also returns
the response and a chat_id for seamless follow-up conversation.

Note: Thorough exploration takes 30s-5min depending on codebase size and task complexity.

## Usage

```python
from servers.repoprompt import manage_workspaces

# Use the tool
result = await manage_workspaces(params)
```

**Note**: This file is auto-generated. Do not edit manually.
