# Module: Hooks & Skills

## Overview

Switch to auto-discovery for hooks (convention over configuration). Headless agents inherit both global and project hooks for consistent behavior.

---

## Hook Auto-Discovery

### Convention

Files in `.claude/hooks/` matching these patterns auto-register:

| Pattern | Event |
|---------|-------|
| `pre-tool-use-*.sh` | PreToolUse |
| `post-tool-use-*.sh` | PostToolUse |
| `user-prompt-submit-*.sh` | UserPromptSubmit |
| `session-start-*.sh` | SessionStart |
| `session-end-*.sh` | SessionEnd |
| `subagent-start-*.sh` | SubagentStart |
| `subagent-stop-*.sh` | SubagentStop |
| `stop-*.sh` | Stop |

### Disable with Underscore Prefix

```bash
# Active hook (auto-discovered)
.claude/hooks/pre-tool-use-validation.sh

# Disabled hook (prefix with _)
.claude/hooks/_pre-tool-use-validation.sh
```

### Discovery Implementation

```python
# scripts/discover_hooks.py
from pathlib import Path
import re

EVENT_PATTERNS = {
    r'^pre-tool-use-': 'PreToolUse',
    r'^post-tool-use-': 'PostToolUse',
    r'^user-prompt-submit-': 'UserPromptSubmit',
    r'^session-start-': 'SessionStart',
    r'^session-end-': 'SessionEnd',
    r'^subagent-start-': 'SubagentStart',
    r'^subagent-stop-': 'SubagentStop',
    r'^stop-': 'Stop',
}

def discover_hooks(hooks_dir: Path) -> dict[str, list[Path]]:
    """Discover hooks from directory."""

    discovered = {event: [] for event in EVENT_PATTERNS.values()}

    for hook_file in hooks_dir.glob('*.sh'):
        name = hook_file.name

        # Skip disabled hooks
        if name.startswith('_'):
            continue

        for pattern, event in EVENT_PATTERNS.items():
            if re.match(pattern, name):
                discovered[event].append(hook_file)
                break

    return discovered
```

---

## Hook Inheritance

### Global + Project Merge

Headless agents load hooks from both:
1. `~/.claude/hooks/` (global)
2. `.claude/hooks/` (project)

```python
def get_hooks_for_event(event: str) -> list[Path]:
    """Get all hooks for an event, merged from global and project."""

    global_hooks = discover_hooks(Path.home() / '.claude' / 'hooks')
    project_hooks = discover_hooks(Path('.claude/hooks'))

    # Project hooks run after global (can override)
    return global_hooks.get(event, []) + project_hooks.get(event, [])
```

### Execution Order

1. Global hooks (alphabetical)
2. Project hooks (alphabetical)
3. First `block` result stops chain

---

## Settings.json Override

Auto-discovery is default. Override in settings.json if needed:

```json
{
  "hooks": {
    "PreToolUse": {
      "discovery": "auto",  // or "manual"
      "disabled": ["pre-tool-use-slow-hook.sh"],
      "order": ["pre-tool-use-critical.sh", "*"]  // * = rest alphabetically
    }
  }
}
```

---

## Hook Invocation Security

> Reference: [00-architecture-decisions.md](./00-architecture-decisions.md) - Hook Security

### JSON Stdin + Subprocess Arrays

Hook invocation MUST follow this security pattern:
1. **JSON over stdin** - Never interpolate data into command line
2. **Subprocess with array** - Use `execFile` with argument array, not shell string

```python
# CORRECT - JSON stdin + subprocess array
import subprocess
import json

data = {"tool_name": tool_name, "params": params}
result = subprocess.run(
    ['python', 'hook_script.py'],
    input=json.dumps(data),
    capture_output=True,
    text=True
)
```

```typescript
// CORRECT - execFile with array
import { execFile } from 'child_process';

execFile('python', [scriptPath], {
    input: JSON.stringify(hookInput)
});

// WRONG - command injection risk
execSync(`python ${script} --data '${JSON.stringify(data)}'`);  // NEVER
```

### Why This Matters

Command injection via string interpolation is a critical security vulnerability. User-controlled data could escape quotes and execute arbitrary commands.

---

## Skill Rules

### Triggers vs Direct Tool Calls

`skill-rules.json` triggers hooks and skill activation - it does NOT make direct tool calls.

| What skill-rules.json Does | What It Does NOT Do |
|---------------------------|---------------------|
| Matches prompt keywords | Call MCP tools directly |
| Activates skills | Execute arbitrary code |
| Co-activates related skills | Bypass hook security |
| Routes to agents | Interpolate user data into commands |

### skill-rules.json Structure

```json
{
  "version": "2.0",
  "skills": {
    "skill-name": {
      "type": "skill",
      "enforcement": "suggest|require|auto",
      "priority": "critical|high|normal|low",
      "description": "What this skill does",
      "promptTriggers": {
        "keywords": ["word1", "word2"],
        "intentPatterns": ["regex1", "regex2"]
      },
      "coActivate": ["other-skill"],
      "coActivateMode": "always|suggest"
    }
  },
  "agents": {
    "agent-name": {
      "type": "agent",
      "description": "What this agent does",
      "promptTriggers": {
        "keywords": ["word1"],
        "intentPatterns": ["regex"]
      }
    }
  },
  "orchestration": {
    "swarm": {
      "type": "pattern",
      "description": "Parallel research",
      "promptTriggers": {
        "keywords": ["swarm", "parallel research", "multiple perspectives"],
        "intentPatterns": ["(run|spawn).*swarm"]
      }
    },
    "sentinel": {
      "type": "pattern",
      "description": "Quality monitoring",
      "promptTriggers": {
        "keywords": ["sentinel", "monitor", "quality check"],
        "intentPatterns": ["(spawn|use).*sentinel"]
      }
    }
  }
}
```

### MCP Code Execution Pattern

Skills use MCP via code execution (not direct tool calls):

```json
{
  "research-agent": {
    "type": "agent",
    "mcpPattern": "code-execution",
    "description": "Research via MCP scripts",
    "scriptPath": "scripts/research_mcp.py"
  }
}
```

Agents inherit this pattern - they use `uv run python scripts/...` rather than MCP tool calls.

---

## Headless Agent Skill Loading

### Same skill-rules.json

Agents use the same `skill-rules.json` as the orchestrator. This ensures:
- Consistent skill activation
- Same trigger keywords
- Same MCP patterns

### Filtering (Future)

If needed, add a filter for headless-inappropriate skills:

```json
{
  "skill-name": {
    "headless": false  // Don't load for headless agents
  }
}
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `.claude/settings.json` | Add `discovery: "auto"` default |
| `.claude/skills/skill-rules.json` | Add orchestration patterns, version 2.0 |

## Files to Create

| File | Purpose |
|------|---------|
| `scripts/discover_hooks.py` | Hook auto-discovery |
| `scripts/merge_hooks.py` | Global + project merging |
