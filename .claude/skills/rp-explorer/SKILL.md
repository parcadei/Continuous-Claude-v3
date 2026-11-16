---
description: Token-efficient codebase exploration using RepoPrompt - USE FIRST for brownfield projects
---

# RP-Explorer Skill

Token-efficient codebase exploration using RepoPrompt CLI. Use this for brownfield projects before planning or debugging.

## When to Use

- Before planning features in an existing codebase
- Before debugging issues
- When you need to understand code structure without reading every file
- When user says "explore", "understand codebase", "how does X work"

## CLI Reference

### Basic Usage
```bash
rp-cli -e '<command>'              # Run single command
rp-cli -e '<cmd1> && <cmd2>'       # Chain commands
rp-cli -w <id> -e '<command>'      # Target specific window
```

### Core Commands

| Command | Aliases | Purpose |
|---------|---------|---------|
| `tree` | - | File/folder tree |
| `structure` | `map` | Code signatures (token-efficient) |
| `search` | `grep` | Search with context |
| `read` | `cat` | Read file contents |
| `select` | `sel` | Manage file selection |
| `context` | `ctx` | Export workspace context |
| `builder` | - | AI-powered file selection |
| `chat` | - | Send to AI chat |

### File Tree
```bash
rp-cli -e 'tree'                    # Full tree
rp-cli -e 'tree --folders'          # Folders only
rp-cli -e 'tree --mode selected'    # Selected files only
```

### Code Structure (TOKEN EFFICIENT)
```bash
rp-cli -e 'structure src/'          # Signatures for path
rp-cli -e 'structure .'             # Whole project
rp-cli -e 'structure --scope selected'  # Selected files only
```

### Search
```bash
rp-cli -e 'search "pattern"'
rp-cli -e 'search "TODO" --extensions .ts,.tsx'
rp-cli -e 'search "error" --context-lines 3'
rp-cli -e 'search "function" --max-results 20'
```

### Read Files
```bash
rp-cli -e 'read path/to/file.ts'
rp-cli -e 'read file.ts --start-line 50 --limit 30'  # Slice
rp-cli -e 'read file.ts --start-line -20'            # Last 20 lines
```

### Selection Management
```bash
rp-cli -e 'select add src/'         # Add to selection
rp-cli -e 'select set src/ lib/'    # Replace selection
rp-cli -e 'select clear'            # Clear selection
rp-cli -e 'select get'              # View selection
```

### Context Export
```bash
rp-cli -e 'context'                 # Full context
rp-cli -e 'context --include prompt,selection,tree'
rp-cli -e 'context --all > output.md'  # Export to file
```

### AI-Powered Builder
```bash
rp-cli -e 'builder "understand auth system"'
rp-cli -e 'builder "find API endpoints" --response-type plan'
```

### Chat
```bash
rp-cli -e 'chat "How does auth work?"'
rp-cli -e 'chat "Design new feature" --mode plan'
```

### Workspaces
```bash
rp-cli -e 'workspace list'          # List workspaces
rp-cli -e 'workspace switch "Name"' # Switch workspace
rp-cli -e 'workspace tabs'          # List tabs
```

## Workflow Shorthand Flags

```bash
# Quick operations without -e syntax
rp-cli --workspace MyProject --select-set src/ --export-context ~/out.md
rp-cli --chat "How does auth work?"
rp-cli --builder "implement user authentication"
```

## Script Files (.rp)

Save repeatable workflows:
```bash
# export.rp
workspace switch MyProject
select set src/
context --all > output.md
```

Run with: `rp-cli --exec-file ~/scripts/export.rp`

## Exploration Workflow

### Step 1: Get Overview
```bash
rp-cli -e 'tree'
rp-cli -e 'structure .'
```

### Step 2: Find Relevant Files
```bash
rp-cli -e 'search "auth" --context-lines 2'
rp-cli -e 'builder "understand authentication"'
```

### Step 3: Deep Dive
```bash
rp-cli -e 'select set src/auth/'
rp-cli -e 'structure --scope selected'
rp-cli -e 'read src/auth/login.ts'
```

### Step 4: Export Context
```bash
rp-cli -e 'context --all > codebase-map.md'
```

## Output

Create codebase-map at: `thoughts/handoffs/<session>/codebase-map.md`

## Notes

- Requires RepoPrompt app with MCP Server enabled
- Use `rp-cli -d <cmd>` for detailed help on any command
- Token-efficient: `structure` gives signatures without full content
