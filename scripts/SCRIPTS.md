# Skills Framework Documentation

**Anthropic's Vision:** Agents build a toolbox of reusable capabilities that evolve over time.

> **Claude Code Optimized:** This framework is designed for [Claude Code](https://docs.claude.com/en/docs/claude-code) (v2.0.20+). Claude Code's filesystem discovery and CLI-based execution enable the 99.6% token reduction. Other AI agents can use the core runtime but may not achieve the same efficiency.

## Philosophy

**DON'T:** Write scripts from scratch each time
**DON'T:** Edit skill files to change parameters (use CLI args instead)
**DO:** Discover and execute skills with CLI arguments
**DO:** Edit skill files to fix bugs or improve logic

**Pattern:**
```
Discover (ls) → Read (cat) → Execute with CLI args (--query, --num-urls, etc.)
```

## Agent Operational Intelligence

**For simple tasks (1 tool call):**
- Use Direct Access (call MCP tool directly)

**For complex workflows (>2 tools, logic, processing):**
1. `ls ./scripts/` - Discover available scripts
2. `cat ./scripts/{script}.py` - Read script documentation and CLI arguments
3. Execute with CLI args:
   ```bash
   uv run python -m runtime.harness scripts/firecrawl_scrape.py \
       --url "https://example.com"
   ```

**For novel workflows:**
1. Explore `./servers/` to discover tools
2. Write NEW skill following CLI template
3. Save to `./skills/` for future reuse
4. Document CLI arguments in docstring

## Efficiency Benefits

**Token savings (for parameter changes):**
- ❌ Writing from scratch: Load schemas + write code = ~5,000 tokens
- ❌ Editing skill to change parameters: Read skill + edit + write = ~800 tokens
- ✅ CLI execution with different args: Read skill + command = ~110 tokens
- **Reduction: 98% (CLI approach)**

**Time savings (for parameter changes):**
- ❌ Writing from scratch: ~2 min
- ❌ Editing skill to change parameters: ~30 sec
- ✅ CLI execution with different args: ~5 sec
- **Reduction: 96% (CLI approach)**

**Note:** Edit skills freely to fix bugs, improve logic, or add features. The efficiency benefit is about avoiding file edits for parameter changes.

## Skill Template (CLI-Based)

```python
"""
SKILL: {Name}

DESCRIPTION: {What it does}

WHEN TO USE: {Use cases}

CLI ARGUMENTS:
    --param1    Description (required/optional, default: value)
    --param2    Description (type: int, default: 123)

USAGE:
    cd /home/khitomer/Projects/mcp-code-execution
    uv run python -m runtime.harness skills/{skill}.py \
        --param1 "value" \
        --param2 456
"""

import argparse
import asyncio
import sys

def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="{Skill description}")
    parser.add_argument("--param1", required=True, help="Description")
    parser.add_argument("--param2", type=int, default=123, help="Description")

    # Filter out script path from sys.argv (harness adds it)
    args_to_parse = [arg for arg in sys.argv[1:] if not arg.endswith(".py")]
    return parser.parse_args(args_to_parse)

async def main():
    """Main skill workflow."""
    args = parse_args()

    print(f"Executing with param1={args.param1}, param2={args.param2}")

    # Use args.param1, args.param2, etc.
    # ...implementation...

    return result

if __name__ == "__main__":
    asyncio.run(main())
```

## Current Scripts Library

| Category | Script | CLI Arguments |
|----------|--------|---------------|
| **Web** | firecrawl_scrape.py | `--url` (required) |
| **Pipeline** | multi_tool_pipeline.py | `--repo-path` (default: "."), `--max-commits` (default: 10) |
| **Search** | perplexity_search.py | `--query` (required) |
| **Docs** | nia_docs.py | `--package`, `--query` |

## Creating New Skills

**When to create:**
- Novel workflow not covered
- Found better pattern
- Specific use case needs

**How to create:**
1. Explore `./servers/` to find needed tools
2. Write skill following CLI template above
3. Add CLI argument parsing with argparse
4. Document in docstring (DESCRIPTION, WHEN TO USE, CLI ARGUMENTS, USAGE)
5. Test thoroughly
6. Save to `./skills/`

**Best practices:**
- Use argparse for all configurable values
- Document all CLI arguments in docstring with types and defaults
- Include USAGE section with concrete example
- Filter sys.argv to remove script path: `[arg for arg in sys.argv[1:] if not arg.endswith(".py")]`
- Keep workflow logic generic/reusable
- Include error handling and progress printing
- Return structured result

## Skills vs Writing Scripts

**Skills (PREFERRED):**
- ✅ Reusable workflow templates
- ✅ CLI arguments for parameter changes (no file edits needed)
- ✅ Edit-friendly for bug fixes and improvements
- ✅ Pre-tested and documented
- ✅ 110 tokens per use (when using CLI args)
- ✅ 5 seconds execution time
- ✅ Agent just reads and executes

**Writing Scripts (ALTERNATIVE):**
- ⚠️ Custom code each time
- ⚠️ Requires schema exploration
- ⚠️ More tokens (~2,000)
- ⚠️ More time (~2 min)
- ⚠️ Agent must write from scratch
- ✅ Good for: Novel workflows, learning, prototyping

## Example Usage

```bash
# Web scraping (requires FIRECRAWL_API_KEY)
uv run python -m runtime.harness scripts/firecrawl_scrape.py \
    --url "https://example.com"

# Multi-tool pipeline (uses git server - works without API keys)
uv run python -m runtime.harness scripts/multi_tool_pipeline.py \
    --repo-path "." \
    --max-commits 5
```

## Key Principles

1. **Parameter Immutability** - Change parameters via CLI args, not by editing the file
2. **Logic Mutability** - Edit skills freely to fix bugs, improve logic, or add features
3. **CLI Parameters** - All configuration via command-line arguments
4. **Reusability** - Write once, use many times with different args
5. **Documentation** - Every skill has USAGE section with example
6. **Type Safety** - argparse provides validation and help text
7. **Efficiency** - 98% token reduction for parameter changes via CLI vs file edits

## Help Text

Every script supports `--help`:

```bash
python scripts/firecrawl_scrape.py --help

# Output:
usage: firecrawl_scrape.py [-h] --url URL

Firecrawl web scraping script

optional arguments:
  -h, --help  show this help message and exit
  --url URL   URL to scrape (required)
```

---

**Remember:** Pass parameters via CLI args, not by editing files. Edit skills freely to fix bugs or improve logic!
