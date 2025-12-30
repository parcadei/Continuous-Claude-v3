# Claude Onboarding

You've been given this repository to understand, extend, or help implement. Here's what you need to know.

---

## What This Is

**Continuous Claude** - A session management system for Claude Code that:
1. Preserves state across `/clear` operations via markdown ledgers
2. Reduces MCP token overhead via lazy-loading code execution
3. Captures reasoning and decisions for future sessions

---

## Core Concepts

### The Problem We Solve

Claude Code's context compaction is lossy. After several compactions, you're working with degraded context (summary of a summary of a summary).

**Our approach:** Clear instead of compact. Save state to external files (ledgers), wipe context clean, reload with full fidelity.

### Key Files

| File | Purpose |
|------|---------|
| `CONTINUITY_CLAUDE-*.md` | Active session state (ephemeral, overwritten each update) |
| `thoughts/handoff/*.md` | Cross-session handoffs (permanent) |
| `thoughts/shared/plans/*.md` | Implementation plans (permanent) |
| `.git/claude/commits/*/reasoning.md` | What was tried per commit (permanent, local) |

### Session Lifecycle

```
Session Start → Ledger auto-loads → Work → Context fills (70%+)
    → Update ledger → /clear → Fresh session → Ledger reloads → Continue
```

---

## Directory Map

```
.claude/
├── skills/           # Skills I can invoke (read SKILL.md files)
├── hooks/            # Event handlers (SessionStart, PostToolUse, etc.)
├── agents/           # Sub-agent configurations
├── rules/            # Behavioral rules (auto-applied)
└── settings.json     # Hook registrations

docs/                 # Human documentation
scripts/              # MCP workflow scripts (Python)
src/runtime/          # MCP execution runtime
servers/              # Generated MCP wrappers (gitignored)
thoughts/             # Research, plans, handoffs (gitignored)
```

---

## Available Skills

### Session Management
- `/continuity_ledger` - Update state before `/clear`
- `/create_handoff` - Save work for new session
- `/resume_handoff` - Resume from handoff document

### Development
- `/create_plan` - Create implementation plan
- `/implement_plan` - Execute plan with verification
- `/validate_plan` - Check implementation against plan
- `/commit` - Git commit without Claude attribution
- `/debug` - Investigate issues

### Research
- `/research` - Document codebase findings
- `/recall-reasoning` - Search past decisions

### MCP Tools
- `/repoprompt` - Codemaps for token-efficient exploration
- `/morph-search` - Fast codebase search (20x grep)
- `/nia-docs` - Library documentation lookup
- `/exa-search` - Web search and code documentation (built-in)
- `/github-search` - GitHub code/repo search
- `/ast-grep-find` - AST-based code patterns

---

## How to Work With This Repo

### If Asked to Implement a Feature

1. **Research first** - Understand existing patterns
   ```
   /research
   ```

2. **Create a plan** - Don't jump to code
   ```
   /create_plan
   ```

3. **Review plan with user** - Get approval before implementing

4. **Implement** - Work through phases
   ```
   /implement_plan
   ```

5. **Handle context limits** - At 70%+, update ledger and `/clear`

6. **Validate** - Check against success criteria
   ```
   /validate_plan
   ```

7. **Commit** - Capture reasoning
   ```
   /commit
   ```

### If Asked to Extend the Kit

Key extension points:

| To Add | Location | Pattern |
|--------|----------|---------|
| New skill | `.claude/skills/<name>/SKILL.md` | Copy existing skill structure |
| New hook | `.claude/hooks/<name>.sh` + `.ts` | Shell wrapper → TypeScript handler |
| New MCP script | `scripts/<name>.py` | CLI args via argparse |
| New rule | `.claude/rules/<name>.md` | YAML frontmatter + markdown |
| New agent | `.claude/agents/<name>.md` | Agent configuration format |

### If Asked to Debug

1. Check hook registrations in `.claude/settings.json`
2. Test hooks manually: `echo '{"type":"resume"}' | .claude/hooks/<hook>.sh`
3. Check MCP config in `mcp_config.json`
4. Regenerate wrappers: `uv run mcp-generate`

---

## Patterns to Follow

### Continuity
- One "Now" item in ledgers (focus)
- Update ledger before `/clear` (not after)
- Use UNCONFIRMED prefix for things to verify after clear

### Skills
- Keep SKILL.md < 200 lines
- Include "When to Use" and "When NOT to Use"
- Reference scripts/ for MCP operations

### Hooks
- Shell wrapper → TypeScript handler pattern
- Return JSON: `{"result": "continue"}` or `{"result": "block", "message": "..."}`

### MCP Scripts
- Use CLI args, not hardcoded values
- Tool IDs: `serverName__toolName` (double underscore)
- Defensive coding for optional fields

---

## Quick Commands

```bash
# Install dependencies
uv sync
cd .claude/hooks && npm install && cd ../..

# Generate MCP wrappers
uv run mcp-generate

# Run MCP script
uv run python -m runtime.harness scripts/<script>.py --help

# Test a hook
echo '{"type":"resume"}' | .claude/hooks/session-start-continuity.sh
```

---

## What to Read

| Priority | Document | Why |
|----------|----------|-----|
| 1 | `docs/WORKFLOW.md` | How users work with Claude |
| 2 | `docs/ARCHITECTURE.md` | Visual system overview |
| 3 | `docs/CONTINUITY.md` | Ledger/handoff details |
| 4 | `CLAUDE.md` | Commands and execution modes |
| 5 | `docs/FAQ.md` | Philosophy and troubleshooting |

---

## Key Constraints

- **Clear > Compact** - Always prefer `/clear` with ledger over compaction
- **Atomic outputs** - Goal isn't to fill context, it's minimal tokens for focused work
- **External state** - Ledgers and thoughts/ are the source of truth, not conversation
