---
name: slash-commands
description: Create and use Claude Code slash commands - quick prompts, bash execution, file references
allowed-tools: [Read, Write, Bash]
---

# Slash Commands Reference

Create and use user-triggered prompts with `/command-name` syntax.

## When to Use

- "How do I create a slash command?"
- "What slash commands are available?"
- "Add bash to my command"
- "Use file references in commands"
- "Slash commands vs skills"

## Built-in Commands

| Command | Purpose |
|---------|---------|
| `/clear` | Clear conversation history |
| `/compact` | Compact conversation with focus |
| `/config` | Open settings interface |
| `/cost` | Show token usage |
| `/agents` | Manage sub-agents |
| `/mcp` | Manage MCP servers |
| `/memory` | Edit CLAUDE.md files |
| `/model` | Select AI model |
| `/review` | Request code review |
| `/resume` | Resume session |
| `/help` | Get usage help |

## Creating Commands

### Project Commands
```bash
mkdir -p .claude/commands
cat > .claude/commands/optimize.md << 'EOF'
---
description: Analyze code for performance issues
---

Review this code for:
- Performance bottlenecks
- Memory leaks
- Caching opportunities
EOF
```

### Personal Commands
```bash
mkdir -p ~/.claude/commands
cat > ~/.claude/commands/review.md << 'EOF'
---
description: Security-focused code review
---

Check for vulnerabilities:
- Input validation
- SQL injection
- XSS risks
EOF
```

## Command File Format

```yaml
---
description: Brief description for /help
allowed-tools: [Bash, Read, Write]  # Optional
argument-hint: "[file] [type]"       # Optional
---

Your markdown instructions here.
Use $1, $2 for arguments or $ARGUMENTS for all.
```

## Bash Execution

Run bash before loading prompt with `!` prefix:

```yaml
---
allowed-tools: Bash(git:*), Bash(grep:*)
description: Git commit helper
---

Current status: !`git status`
Staged changes: !`git diff --staged`
Recent commits: !`git log --oneline -5`

Based on these changes, suggest a commit message.
```

**Rules:**
- Must declare `allowed-tools: Bash(...)` in frontmatter
- Use backticks: `` !`command` ``
- Output is included in Claude's context

## File References

Include files with `@` prefix:

```markdown
Review against @.claude/STYLE_GUIDE.md

Compare:
- @src/old.js
- @src/new.js

Refactor files matching @src/**/*.util.ts
```

## Arguments

```yaml
---
argument-hint: "[pr-number] [priority]"
---

Review PR #$1 with priority: $2

# Or use all arguments:
Fix issue #$ARGUMENTS
```

**Usage:**
```bash
/review-pr 456 high
# $1 = "456", $2 = "high"
```

## Namespacing

Organize with subdirectories:

```
.claude/commands/
├── frontend/
│   └── component.md    → /component (project:frontend)
└── backend/
    └── endpoint.md     → /endpoint (project:backend)
```

## MCP Slash Commands

MCP servers expose prompts as commands:

```bash
/mcp__github__list_prs
/mcp__github__pr_review 456
/mcp__jira__create_issue "Bug" high
```

## Slash Commands vs Skills

| Aspect | Slash Commands | Skills |
|--------|----------------|--------|
| Invocation | Explicit: `/command` | Auto-discovered |
| Files | Single .md file | Directory with SKILL.md |
| Use Case | Quick prompts | Complex workflows |

**Use slash commands for:** Frequently typed prompts, simple templates
**Use skills for:** Complex workflows, multiple files, auto-discovery

## Example: Complete Git Commit Command

```yaml
---
description: Generate semantic commit message
allowed-tools: Bash(git:*), Read
argument-hint: "[type]"
---

# Semantic Commit Generator

Staged files: !`git diff --name-only --cached`

Diff preview:
!`git diff --cached | head -100`

Generate a conventional commit message.
Type: $1 (feat/fix/docs/style/refactor/perf/test/chore)

Format: `<type>(<scope>): <subject>`
```

**Usage:** `/commit feat`
