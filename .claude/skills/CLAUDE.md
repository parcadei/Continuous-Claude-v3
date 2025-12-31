# Skills System

Skills are Claude Code's native format for reusable expert tools. Auto-discovered from this directory.

## What is a Skill?

A self-contained tool that:
- Defines trigger patterns (when to activate)
- Provides methodology (step-by-step instructions)
- Integrates with MCP tools
- Returns results or artifacts

## SKILL.md Format

```yaml
---
name: my-skill
description: Brief description (max 1024 chars)
---

# My Skill

Instructions for Claude...
```

## Skill Categories

| Category | Skills |
|----------|--------|
| **Exploration** | rp-explorer, repo-research-analyst, research, morph-search, github-search, ast-grep-find |
| **Planning** | create_plan, plan-agent, validate-agent, nia-docs |
| **Implementation** | implement_plan, implement_task, morph-apply, test-driven-development, commit |
| **Debugging** | debug, debug-agent, debug-hooks, hook-developer, braintrust-analyze |
| **Context** | continuity_ledger, create_handoff, resume_handoff, recall-reasoning |
| **Learning** | compound-learnings, skill-developer, describe_pr, qlty-check |
| **Research** | perplexity-search, firecrawl-scrape, repoprompt |
| **Documentation** | upgrade-claude-documentation |

## Activation

Skills auto-activate via `skill-rules.json`:
- **Keywords**: Exact phrase matches
- **Intent patterns**: Regex-based matching
- **File context**: Files being viewed/edited

## Creating Skills

1. Create `.claude/skills/my-skill/SKILL.md`
2. Add to `skill-rules.json`:
```json
{
  "my-skill": {
    "promptTriggers": {
      "keywords": ["my feature"]
    }
  }
}
```

## Skills vs Agents

| Aspect | Skills | Agents |
|--------|--------|--------|
| Discovery | Auto-discovered | Spawned explicitly |
| Context | Main conversation | Separate context |
| Complexity | Medium workflows | Complex multi-step |
