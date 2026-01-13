# Contributing to Continuous Claude

Thank you for your interest in contributing! This guide covers how to add skills, agents, hooks, and extend TLDR.

## Table of Contents

- [Development Setup](#development-setup)
- [Adding Skills](#adding-skills)
- [Creating Agents](#creating-agents)
- [Developing Hooks](#developing-hooks)
- [Extending TLDR](#extending-tldr)
- [Code Style](#code-style)
- [Testing](#testing)
- [Documentation Validation](#documentation-validation)
- [Pull Request Process](#pull-request-process)

---

## Development Setup

```bash
# Clone (your fork) of the repository
cd Continuous-Claude-v3/opc

# Install Python dependencies
uv sync

# Install hook dependencies (TypeScript)
cd ../.claude/hooks && npm install && npm run build && cd ../../opc

# Verify installation
claude
> /help
```

---

## Adding Skills

Skills are modular capabilities defined in `.claude/skills/<skill-name>/SKILL.md`.

### Skill Structure

```
.claude/skills/my-skill/
├── SKILL.md          # Main skill definition (required)
└── templates/        # Optional templates
```

### SKILL.md Format

```markdown
# my-skill

Short description of what this skill does.

## When to Use

- Trigger condition 1
- Trigger condition 2

## Workflow

1. Step one
2. Step two
3. Step three

## Commands

| Command | Description |
|---------|-------------|
| `/my-skill` | Main invocation |
| `/my-skill --option` | With options |

## Example

User: "do my-skill thing"
Claude: [executes skill workflow]
```

### Registering Skill Triggers

Add to `.claude/skills/skill-rules.json`:

```json
{
  "skill": "my-skill",
  "keywords": ["my-skill", "specific trigger"],
  "intentPatterns": ["do.*my.*skill"],
  "priority": 50
}
```

### Quick Skill Creation

```
> /skill-developer
```

This interactive skill walks you through creating new skills.

---

## Creating Agents

Agents are specialized AI workers defined in `.claude/agents/<agent-name>.md`.

### Agent Structure

```markdown
# Frontmatter
---
name: <name of agent>
description: <one line description of agent>
model: <preferred model: opus | sonnet | haiku>
tools: <list tools agent needs (optional): Read | Grep | Glob | etc...>
---

## Prompt

<system>
You are the agent-name agent for Continuous Claude.

Your job is to:
1. Specific task
2. Another task

## Constraints

- Constraint 1
- Constraint 2

## Output Format

Return results as:
[format description]
</system>
```

### Agent Types

| Type | Model | Use Case |
|------|-------|----------|
| **Orchestrator** | Opus | Coordinate multi-agent workflows |
| **Researcher** | Sonnet/Opus | Explore codebase or external sources |
| **Implementer** | Opus | Write/modify code |
| **Reviewer** | Opus | Analyze and critique |
| **Specialist** | Varies | Domain-specific tasks |

### Spawning Agents

Agents are spawned via the Task tool:

```typescript
Task({
  subagent_type: "my-agent",
  prompt: "Do the thing",
  description: "Doing the thing"
})
```

---

## Developing Hooks

Hooks intercept Claude Code at lifecycle points. Located in `.claude/hooks/`.

### Hook Types

| Lifecycle | When it runs |
|-----------|--------------|
| `SessionStart` | Session begins |
| `SessionEnd` | Session ends |
| `PreToolUse` | Before tool execution |
| `PostToolUse` | After tool execution |
| `UserPromptSubmit` | User sends a message |
| `PreCompact` | Before context compaction |
| `Stop` | LLM generation stops |

### Shell Hook Template

```bash
#!/bin/bash
# .claude/hooks/my-hook.sh

# Read input from stdin (JSON)
INPUT=$(cat)

# Parse relevant fields
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // empty')

# Your logic here
if [[ "$TOOL_NAME" == "Read" ]]; then
    # Do something
    echo '{"result": "modified content"}'
else
    # Pass through
    echo "$INPUT"
fi
```

### TypeScript Hook Template

```typescript
// .claude/hooks/src/my-hook.ts
interface HookInput {
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  session_id?: string;
}

interface HookOutput {
  result?: string;
  permissionDecision?: 'allow' | 'deny';
  reason?: string;
}

async function hook(input: HookInput): Promise<HookOutput> {
  // Your logic here
  return { result: 'success' };
}

// Entry point
const input: HookInput = JSON.parse(
  require('fs').readFileSync(0, 'utf-8')
);
hook(input).then(output => console.log(JSON.stringify(output)));
```

### Registering Hooks

Add to `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read",
        "hooks": [
          {
            "command": ".claude/hooks/my-hook.sh",
            "timeout": 5000
          }
        ]
      }
    ]
  }
}
```

### Hook Development Workflow

```
> /hook-developer
```

Or debug existing hooks:

```
> /debug-hooks
```

---

## Extending TLDR

TLDR is the 5-layer code analysis system installed as a pip package (`llm-tldr`).

### Architecture

```
tldr/
├── api.py              # Unified API (all layers)
├── ast_extractor.py    # L1: AST extraction
├── hybrid_extractor.py # Multi-language support
├── cross_file_calls.py # L2: Call graph
├── cfg_extractor.py    # L3: Control flow
├── dfg_extractor.py    # L4: Data flow
└── pdg_extractor.py    # L5: Program dependence
```

### Adding Language Support

1. Add tree-sitter grammar:
```bash
uv pip install tree-sitter-<language>
```

2. Update `hybrid_extractor.py`:
```python
LANGUAGE_CONFIGS = {
    'mylang': LanguageConfig(
        extension='.ml',
        tree_sitter_lang='mylang',
        function_patterns=['function_definition'],
        class_patterns=['class_definition']
    )
}
```

3. Add tests in `tests/test_mylang.py`

### Running TLDR Tests

```bash
# TLDR is installed via pip
pip show llm-tldr

# Run tests if available
python -m pytest -v
```

---

## Code Style

### Python

- Use type hints
- Format with `ruff`
- Follow PEP 8

### TypeScript

- Use strict mode
- Format with Prettier
- Follow existing patterns

### Markdown

- Use CommonMark
- Keep lines under 100 chars
- Use tables for structured data

---

## Testing

### Running All Tests

```bash
# TLDR tests
pip show llm-tldr && python -m pytest -v

# Hook tests (TypeScript)
cd .claude/hooks && npm test
```

### Testing Skills

```bash
# Manual test in Claude
> /my-skill

# Check skill-rules.json triggers
> "trigger phrase that should activate my-skill"
```

### Testing Hooks

```bash
# Test hook directly
echo '{"tool_name": "Read", "tool_input": {"file_path": "test.py"}}' | .claude/hooks/my-hook.sh
```

---

## Documentation Validation

This project uses automated validation to prevent documentation drift and ensure consistency between code and documentation.

### Pre-commit Hooks

Pre-commit hooks automatically validate and fix issues before commits:

```bash
# Install pre-commit hooks
pre-commit install --config .pre-commit-config.yaml

# Run hooks manually on all files
pre-commit run --config .pre-commit-config.yaml --all-files

# Run specific hook
pre-commit run --config .pre-commit-config.yaml update-doc-counts
```

### Available Hooks

| Hook | Purpose | When It Runs |
|------|---------|--------------|
| `update-doc-counts` | Auto-updates skills/hooks/agents counts in README.md | Push stage |
| `doc-counts-validate` | Validates documented counts match actual counts | Push stage |
| `schema-drift-check` | Validates init-db.sql against running database | Push stage |
| `markdown-links-validate` | Checks for broken internal links | Commit/Push |
| `yaml-consistency-check` | Validates YAML syntax and keys | Commit/Push |

### CI Validation

GitHub Actions runs additional validation on pull requests:

| Job | Purpose |
|-----|---------|
| `markdownlint` | Lints markdown files for style issues |
| `link-check` | Checks all links are valid (using lychee) |
| `count-validation` | Verifies documented counts match reality |
| `update-counts` | Auto-commits updated counts to PRs |

### Auto-updates

Documentation counts (skills, hooks, agents) are automatically updated in PRs:

1. When you add/remove skills, hooks, or agents
2. The `update-doc-counts` hook runs on push
3. A CI job commits the updated counts to your branch
4. Merge conflicts are avoided by running before PR merge

### What Gets Auto-Updated

- `README.md` - Badge counts, TOC references, section headers
- `CONTRIBUTING.md` - Any count references

Counts are derived from:
- Skills: `.claude/skills/*/SKILL.md`
- Hooks: `.claude/hooks/dist/*.mjs`
- Agents: `.claude/agents/*.md`

---

## Pull Request Process

1. **Fork** the repository
2. **Create branch**: `git checkout -b feature/my-feature`
3. **Make changes** following the guidelines above
4. **Test** your changes
5. **Commit** with clear message
6. **Push** to your fork
7. **Open PR** with:
   - Description of changes
   - Testing done
   - Any breaking changes

### PR Checklist

- [ ] Tests pass
- [ ] Documentation updated
- [ ] Documentation counts auto-updated (CI will handle)
- [ ] No breaking changes (or documented)
- [ ] Follows code style

---

## Getting Help

- Open an issue for bugs or feature requests
- Use `/help` in Claude for usage questions
- Check existing skills/agents for patterns

Thank you for contributing!
