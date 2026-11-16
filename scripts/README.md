# Scripts - CLI-Based MCP Workflows

**Purpose:** Agent-agnostic, reusable Python scripts with CLI arguments for MCP tool orchestration.

---

## What Are Scripts?

**Scripts** are CLI-based Python workflows that:
- Accept parameters via command-line arguments (argparse)
- Orchestrate MCP tool calls
- Return structured results
- Work with ANY AI agent (not just Claude Code)

**NOT to be confused with:**
- **Skills** = Claude Code's native format (.claude/skills/ with SKILL.md)

---

## Example Scripts

**This directory contains MCP workflow scripts:**

### firecrawl_scrape.py
- Web scraping pattern
- CLI: `--url` (required)
- Requires: `FIRECRAWL_API_KEY`

### multi_tool_pipeline.py
- Multi-tool chaining pattern (git analysis)
- CLI: `--repo-path` (default: "."), `--max-commits` (default: 10)
- Works without API keys (uses git server)

### Math Cognitive Prosthetics

**sympy_compute.py**
- Symbolic math: solve, integrate, differentiate, simplify
- CLI: `solve "expr" --var x --domain real`, `integrate "expr" --var x --bounds 0 1`
- Requires: sympy (included in deps)

**z3_solve.py**
- Constraint solving: sat, prove, optimize
- CLI: `sat "constraints" --type int`, `prove "theorem" --vars x y --type int`
- Requires: z3-solver (included in deps)

**math_scratchpad.py**
- Step-by-step verification
- CLI: `verify "step"`, `chain --steps '[...]'`, `explain "step"`
- Uses SymPy + Z3 internally

### Other scripts
See `ls scripts/` for all available workflows (perplexity, github, nia, etc.)

---

## Usage

**Execute scripts with CLI arguments:**

```bash
# Web scraping (requires FIRECRAWL_API_KEY)
uv run python -m runtime.harness scripts/firecrawl_scrape.py \
    --url "https://example.com"

# Multi-tool pipeline (works without API keys)
uv run python -m runtime.harness scripts/multi_tool_pipeline.py \
    --repo-path "." \
    --max-commits 5
```

**Key:** Parameters via CLI args - edit scripts freely to fix bugs or improve logic

---

## Scripts vs Skills

### Scripts (This Directory)

**What:** CLI-based Python workflows
**Where:** `./scripts/`
**Format:** Python with argparse
**Discovery:** Manual (ls, cat)
**For:** Any AI agent
**Efficiency:** 99.6% token reduction with CLI args

### Skills (Claude Code Native)

**What:** SKILL.md directories
**Where:** `.claude/skills/`
**Format:** YAML + markdown
**Discovery:** Auto (Claude Code scans)
**For:** Claude Code only
**Efficiency:** Native progressive disclosure

**Relationship:** Skills reference scripts for execution

---

## Creating Custom Scripts

Follow the template pattern:

```python
"""
SCRIPT: Your Script Name
DESCRIPTION: What it does
CLI ARGUMENTS:
    --param    Description
USAGE:
    uv run python -m runtime.harness scripts/your_script.py --param "value"
"""

import argparse
import asyncio
import sys

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--param", required=True)
    args_to_parse = [arg for arg in sys.argv[1:] if not arg.endswith(".py")]
    return parser.parse_args(args_to_parse)

async def main():
    args = parse_args()
    # Your MCP orchestration logic
    return result

asyncio.run(main())
```

---

## Documentation

- **SCRIPTS.md** - Complete framework documentation
- **This README** - Quick start
- **../.claude/skills/** - Claude Code Skills that reference these scripts
- **../docs/** - Complete project documentation

---

**Remember:** Scripts = Agent-agnostic CLI workflows. Skills = Claude Code native format.
