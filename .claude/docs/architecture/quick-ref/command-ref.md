# Command Reference

## Core Workflows

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/ralph` | Full product build | PRD → Design → Implement |
| `/maestro` | Multi-agent orchestration | Complex multi-step tasks |
| `/fix` | Bug resolution | Debug → Fix → Test |
| `/build` | Feature development | Plan → Implement → Review |
| `/explore` | Codebase research | Understanding code |
| `/review` | Code review | Before merge |
| `/release` | Release prep | Audit → Test → Changelog |

## Research Commands

| Command | Purpose |
|---------|---------|
| `/explore quick` | Surface scan |
| `/explore deep` | Full analysis |
| `/explore "<query>"` | Targeted search |
| `/recall "<query>"` | Search memory |

## Memory Commands

| Command | Purpose |
|---------|---------|
| `/recall "<query>"` | Search past learnings |
| `/memory store` | Store new learning |

## ROADMAP Commands

| Command | Purpose |
|---------|---------|
| `/roadmap show` | Display current ROADMAP state |
| `/roadmap add <item>` | Add item to Planned section |
| `/roadmap focus <item>` | Set Current Focus |
| `/roadmap complete` | Mark current goal done |

## Git Commands

| Command | Purpose |
|---------|---------|
| `/commit` | Create commit with approval |
| `/git status` | Show git status |

## Task Management

| Command | Purpose |
|---------|---------|
| `/task list` | Show active tasks |
| `/task create` | Create new task |
| `/task resume` | Resume from handoff |

## Utility Commands

| Command | Purpose |
|---------|---------|
| `/help` | Show available commands |
| `/compact` | Compact context |
| `/clear` | Clear conversation |

## Skill Activation

Skills auto-activate on keywords:

| Keyword Pattern | Skill |
|-----------------|-------|
| "debug", "error", "fix" | systematic-debugging |
| "database", "SQL" | databases |
| "PR", "review" | code-review |
| MCP tool use | mcp-guidance |

## CLI Flags

| Flag | Effect |
|------|--------|
| `--think` | Standard extended thinking |
| `--think-hard` | Deep extended thinking |
| `--ultrathink` | Maximum extended thinking |
| `--uc` | Ultra-compressed output |

## Quick Reference

```
Research:     /explore, /recall, scout, oracle
Implement:    /build, /fix, kraken, spark
Review:       /review, critic, judge
Release:      /release, /commit
Orchestrate:  /ralph, /maestro
```

## Agent Shortcuts

| Shorthand | Full Agent |
|-----------|------------|
| scout | Codebase exploration |
| oracle | External research |
| kraken | TDD implementation |
| spark | Quick fixes |
| arbiter | Test runner |
