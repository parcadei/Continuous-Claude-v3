---
name: sub-agents
description: Create and configure Claude Code sub-agents with custom prompts, tools, and models
allowed-tools: [Read, Write, Bash]
---

# Sub-Agents Reference

Create specialized AI agents with isolated contexts for specific tasks.

## When to Use

- "How do I create a sub-agent?"
- "Configure agent tools"
- "What built-in agents exist?"
- "Agent model selection"
- "Agent chaining patterns"

## Quick Start

### Interactive (Recommended)
```bash
/agents
```
Opens menu to create, edit, and manage agents.

### Manual Creation
```bash
mkdir -p .claude/agents
cat > .claude/agents/reviewer.md << 'EOF'
---
name: reviewer
description: Code review specialist. Use proactively after code changes.
tools: Read, Grep, Glob, Bash
model: sonnet
---

You are a senior code reviewer focusing on quality and security.

## Review Checklist
- Code clarity and naming
- Error handling
- Security vulnerabilities
- Test coverage
EOF
```

### CLI-Based
```bash
claude --agents '{
  "reviewer": {
    "description": "Code reviewer",
    "prompt": "Review for quality and security",
    "tools": ["Read", "Bash"],
    "model": "sonnet"
  }
}'
```

## Agent File Format

```yaml
---
name: agent-name
description: When/why to use this agent
tools: Read, Edit, Bash      # Optional, inherits all if omitted
model: sonnet                 # sonnet, opus, haiku, inherit
---

System prompt content here...
```

## Configuration Fields

| Field | Required | Options |
|-------|----------|---------|
| `name` | Yes | lowercase, hyphens |
| `description` | Yes | When to use |
| `tools` | No | Tool list (inherits all if omitted) |
| `model` | No | `sonnet`, `opus`, `haiku`, `inherit` |

## Built-In Agents

| Agent | Model | Tools | Purpose |
|-------|-------|-------|---------|
| General-purpose | Sonnet | All | Complex multi-step tasks |
| Plan | Sonnet | Read-only | Plan mode research |
| Explore | Haiku | Read-only | Fast codebase search |

## Model Selection

| Model | Speed | Best For |
|-------|-------|----------|
| Haiku | Fastest | Search, quick lookups |
| Sonnet | Fast | Most tasks (default) |
| Opus | Slower | Complex reasoning |

## Tool Combinations

```yaml
# Code Reviewer (read-only)
tools: Read, Grep, Glob, Bash

# Debugger
tools: Read, Edit, Bash, Grep, Glob

# Implementer
tools: Read, Write, Edit, Bash, Glob
```

## Example Agents

### Code Reviewer
```yaml
---
name: code-reviewer
description: Reviews code for quality and security. Use after code changes.
tools: Read, Grep, Glob, Bash
model: sonnet
---

Review code for:
- Security vulnerabilities
- Code quality issues
- Missing error handling
- Test coverage gaps

Output findings by priority: Critical > Warning > Suggestion
```

### Debugger
```yaml
---
name: debugger
description: Debug errors and test failures.
tools: Read, Edit, Bash, Grep, Glob
model: inherit
---

Debugging process:
1. Capture error details
2. Identify failure location
3. Form hypotheses
4. Test and verify
5. Implement fix
```

## File Locations

| Type | Location | Priority |
|------|----------|----------|
| Project | `.claude/agents/` | Highest |
| User | `~/.claude/agents/` | Lower |

## Advanced Patterns

### Resumable Agents
```
[Agent returns agentId: "abc123"]

# Later: resume with context
claude -r "abc123" "Continue analysis"
```

### Agent Chaining
```
Use code-analyzer to find issues,
then use optimizer to fix them
```

## Best Practices

1. **Single responsibility** - One clear purpose per agent
2. **Restrict tools** - Only grant what's needed
3. **Clear descriptions** - Action-oriented, include "proactively"
4. **Version control** - Check `.claude/agents/` into git
