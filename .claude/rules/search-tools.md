# Search Tool Hierarchy

When searching code, use this decision tree:

## Decision Tree

```
Need to understand code STRUCTURE?
  (find function calls, class usages, refactor patterns)
  → Use AST-grep (/ast-grep-find)

Need to find TEXT in code?
  → Use Morph (/morph-search) - 20x faster
  → If no Morph API key: fall back to Grep tool

Simple one-off search?
  → Use built-in Grep tool directly
```

## Tool Comparison

| Tool | Best For | Requires |
|------|----------|----------|
| **AST-grep** | Semantic patterns: "find all calls to `foo()`", refactoring, find usages by type | MCP server |
| **Morph** | Fast text search: "find files mentioning error", grep across codebase | API key |
| **Grep** | Simple patterns, fallback when Morph unavailable | Nothing (built-in) |

## Examples

**AST-grep** (structural):
- "Find all functions that return a Promise"
- "Find all React components using useState"
- "Refactor all imports of X to Y"

**Morph** (text search):
- "Find all files mentioning 'authentication'"
- "Search for TODO comments"
- "Find error handling patterns"

**Grep** (fallback):
- Simple keyword search when Morph unavailable
- Quick checks in a few files
